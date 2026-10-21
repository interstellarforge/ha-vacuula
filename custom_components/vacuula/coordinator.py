"""Data coordinator: live robot state through SSE, with a polling fallback."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    VacuulaClient,
    VacuulaCommandError,
    VacuulaConnectionError,
    VacuulaError,
)
from .const import (
    ABILITY_START,
    ABILITY_STATE,
    DEFAULT_CLEANING_MODE,
    DEFAULT_NAVIGATION_MODE,
    DOMAIN,
    POLL_INTERVAL,
    ROBOT_TYPE_GEN4,
)

_LOGGER = logging.getLogger(__name__)

type VacuulaConfigEntry = ConfigEntry[VacuulaCoordinator]


@dataclass
class RobotData:
    """Latest known state of one robot."""

    serial: str
    name: str
    label_serial: str | None = None
    connected: bool = False
    state: str | None = None
    action: str | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)
    available_commands: dict[str, bool] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    def apply_state(self, body: dict[str, Any]) -> None:
        """Merge a robot state body (state.show response or peer.state event)."""
        self.state = body.get("state", self.state)
        self.action = body.get("action", self.action)
        self.errors = body.get("errors") or []
        self.available_commands = body.get("available_commands", {}) or {}
        self.details = body.get("details", {}) or {}


class VacuulaCoordinator(DataUpdateCoordinator[dict[str, RobotData]]):
    """Keeps all Gen4 robots of one Vacuula server up to date."""

    config_entry: VacuulaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VacuulaConfigEntry,
        client: VacuulaClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=POLL_INTERVAL,
        )
        self.client = client
        self.cleaning_settings: dict[str, dict[str, str]] = {}
        self._streams: dict[str, asyncio.Task] = {}
        self._events_task: asyncio.Task | None = None

    # ---- polling ---------------------------------------------------------

    async def _async_update_data(self) -> dict[str, RobotData]:
        try:
            robots = await self.client.get_robots()
        except VacuulaError as err:
            raise UpdateFailed(f"Cannot reach Vacuula server: {err}") from err

        previous = self.data or {}
        data: dict[str, RobotData] = {}
        for serial, info in robots.items():
            if info.get("type") != ROBOT_TYPE_GEN4:
                continue  # Gen3 robots use a different protocol: not supported yet
            robot = previous.get(serial) or RobotData(serial=serial, name=serial)
            robot.name = info.get("name") or serial
            robot.label_serial = info.get("label_serial")
            robot.connected = bool(info.get("connected"))
            if robot.connected:
                await self._refresh_state(robot)
            data[serial] = robot
            self.cleaning_settings.setdefault(
                serial,
                {
                    "mode": DEFAULT_CLEANING_MODE,
                    "navigation_mode": DEFAULT_NAVIGATION_MODE,
                },
            )
        return data

    async def _refresh_state(self, robot: RobotData) -> None:
        try:
            result = await self.client.command(
                robot.serial, {"ability": ABILITY_STATE}
            )
        except VacuulaError as err:
            _LOGGER.debug("state.show failed for %s: %s", robot.serial, err)
            return
        body = result.get("body")
        if isinstance(body, dict):
            robot.apply_state(body)

    # ---- live updates ----------------------------------------------------

    def start_listeners(self) -> None:
        """Start the SSE listeners (cancelled automatically on unload)."""
        entry = self.config_entry
        self._events_task = entry.async_create_background_task(
            self.hass, self._events_loop(), f"{DOMAIN}_events"
        )
        entry.async_on_unload(self.async_add_listener(self._ensure_streams))
        self._ensure_streams()

    def _ensure_streams(self) -> None:
        for serial in self.data or {}:
            task = self._streams.get(serial)
            if task is None or task.done():
                self._streams[serial] = self.config_entry.async_create_background_task(
                    self.hass,
                    self._robot_loop(serial),
                    f"{DOMAIN}_robot_{serial}",
                )

    async def _events_loop(self) -> None:
        """Server-wide stream: robots (dis)connecting or being renamed."""
        await self._run_stream("/events", self._on_server_event)

    async def _on_server_event(self, event: str, payload: Any) -> None:
        if event != "robots" or not isinstance(payload, dict) or not self.data:
            return
        changed = False
        for serial, info in payload.items():
            robot = self.data.get(serial)
            if robot is None:
                changed = True  # new robot: do a full refresh
                continue
            connected = bool(info.get("connected"))
            if connected != robot.connected or info.get("name") != robot.name:
                changed = True
        if changed:
            await self.async_request_refresh()

    async def _robot_loop(self, serial: str) -> None:
        async def handler(_event: str, payload: Any) -> None:
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, dict):
                return
            if (data.get("to") or {}).get("service") != "peer.state":
                return
            body = data.get("body")
            robot = (self.data or {}).get(serial)
            if robot is None or not isinstance(body, dict):
                return
            robot.connected = True
            robot.apply_state(body)
            self.async_set_updated_data(self.data)

        await self._run_stream(f"/robot/{serial}/connect", handler, on_open=serial)

    async def _run_stream(self, path: str, handler, on_open: str | None = None):
        backoff = 2
        while True:
            try:
                async for event, payload in self.client.stream(path):
                    backoff = 2
                    await handler(event, payload)
            except asyncio.CancelledError:
                raise
            except VacuulaCommandError as err:
                _LOGGER.debug("Stream %s refused: %s", path, err)
            except VacuulaConnectionError as err:
                _LOGGER.debug("Stream %s dropped: %s", path, err)
            except Exception:  # noqa: BLE001 - never let the listener die
                _LOGGER.exception("Unexpected error in stream %s", path)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
            if on_open is not None:
                # Catch up on anything missed while the stream was down.
                await self.async_request_refresh()

    # ---- commands --------------------------------------------------------

    async def async_command(
        self, serial: str, payload: dict[str, Any], refresh: bool = True
    ) -> dict[str, Any]:
        """Send a command to the robot, turning failures into HA errors."""
        try:
            result = await self.client.command(serial, payload)
        except VacuulaCommandError as err:
            raise HomeAssistantError(
                f"Robot refused '{payload.get('ability')}': {err.message} ({err.status})"
            ) from err
        except VacuulaConnectionError as err:
            raise HomeAssistantError(f"Cannot reach Vacuula: {err}") from err
        if refresh:
            robot = (self.data or {}).get(serial)
            if robot is not None:
                await self._refresh_state(robot)
                self.async_set_updated_data(self.data)
        return result

    async def async_start_cleaning(
        self,
        serial: str,
        *,
        map_ref: str | None = None,
        zones: list[str] | None = None,
        mode: str | None = None,
        navigation_mode: str | None = None,
        nogo_enabled: bool = True,
        use_map: bool = True,
    ) -> None:
        """Start a (zone) cleaning, resolving map/zone names to ids."""
        settings = {
            "mode": mode or self.cleaning_settings[serial]["mode"],
            "navigation_mode": navigation_mode
            or self.cleaning_settings[serial]["navigation_mode"],
        }
        runs: list[dict[str, Any]]
        floorplan = None
        if use_map:
            # With a promoted map the robot honours no-go lines; without one it
            # just does a plain full clean.
            floorplan = await self._resolve_map(
                serial, map_ref, required=bool(map_ref or zones)
            )
        if floorplan is None:
            runs = [{"map": None, "settings": settings}]
        elif not zones:
            runs = [
                {
                    "map": {
                        "rank_id": floorplan["id"],
                        "track_id": None,
                        "nogo_enabled": nogo_enabled,
                    },
                    "settings": settings,
                }
            ]
        else:
            zone_ids = await self._resolve_zones(serial, floorplan, zones)
            runs = [
                {
                    "map": {
                        "rank_id": floorplan["id"],
                        "track_id": zid,
                        "nogo_enabled": nogo_enabled,
                    },
                    "settings": settings,
                }
                for zid in zone_ids
            ]
        await self.async_command(serial, {"ability": ABILITY_START, "runs": runs})

    async def _resolve_map(
        self, serial: str, map_ref: str | None, required: bool
    ) -> dict[str, Any] | None:
        try:
            maps = await self.client.get_maps(serial)
        except VacuulaError as err:
            if required:
                raise HomeAssistantError(f"Cannot load maps: {err}") from err
            return None
        if not isinstance(maps, list):
            maps = []
        if map_ref:
            ref = map_ref.casefold()
            for floorplan in maps:
                if ref in (str(floorplan.get("id", "")).casefold(),
                           str(floorplan.get("name", "")).casefold()):
                    found = floorplan
                    break
            else:
                names = ", ".join(str(m.get("name")) for m in maps) or "none"
                raise ServiceValidationError(
                    f"Map '{map_ref}' not found (available: {names})"
                )
        else:
            found = next((m for m in maps if m.get("promoted")), None)
            if found is None:
                if required:
                    raise ServiceValidationError(
                        "No active (promoted) map on the robot. Activate a map "
                        "in the Vacuula app first."
                    )
                return None
        if not found.get("promoted"):
            raise ServiceValidationError(
                f"Map '{found.get('name')}' is not active on the robot. "
                "Activate it in the Vacuula app first."
            )
        return found

    async def _resolve_zones(
        self, serial: str, floorplan: dict[str, Any], zones: list[str]
    ) -> list[str]:
        boundaries = await self.client.get_boundaries(serial, floorplan["id"])
        cleaning = [
            b for b in boundaries if b.get("function") == "cleaning" and b.get("enabled", True)
        ]
        ids: list[str] = []
        for ref in zones:
            key = ref.casefold()
            match = next(
                (
                    b for b in cleaning
                    if key in (str(b.get("id", "")).casefold(), str(b.get("name", "")).casefold())
                ),
                None,
            )
            if match is None:
                names = ", ".join(str(b.get("name")) for b in cleaning) or "none"
                raise ServiceValidationError(
                    f"Zone '{ref}' not found on map '{floorplan.get('name')}' "
                    f"(available: {names})"
                )
            ids.append(match["id"])
        return ids

    async def async_get_zones(
        self, serial: str, map_ref: str | None
    ) -> dict[str, Any]:
        """Describe maps and their cleaning zones (service response)."""
        maps = await self.client.get_maps(serial)
        result = []
        for floorplan in maps:
            if map_ref and map_ref.casefold() not in (
                str(floorplan.get("id", "")).casefold(),
                str(floorplan.get("name", "")).casefold(),
            ):
                continue
            boundaries = await self.client.get_boundaries(serial, floorplan["id"])
            result.append(
                {
                    "id": floorplan["id"],
                    "name": floorplan.get("name"),
                    "active": bool(floorplan.get("promoted")),
                    "zones": [
                        {"id": b["id"], "name": b.get("name"), "enabled": b.get("enabled", True)}
                        for b in boundaries
                        if b.get("function") == "cleaning"
                    ],
                    "nogo": [
                        {"id": b["id"], "name": b.get("name"), "enabled": b.get("enabled", True)}
                        for b in boundaries
                        if b.get("function") == "nogo"
                    ],
                }
            )
        return {"maps": result}
