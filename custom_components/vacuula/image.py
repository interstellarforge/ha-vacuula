"""Image entities: the active map and the path of the last cleaning."""

from __future__ import annotations

from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import VacuulaConfigEntry, VacuulaCoordinator
from .entity import VacuulaEntity, async_add_robot_entities
from .mapimage import render_map


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VacuulaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_robot_entities(
        entry,
        async_add_entities,
        lambda c, s: [ActiveMapImage(hass, c, s), LastRunImage(hass, c, s)],
    )


class _MapImage(VacuulaEntity, ImageEntity):
    """Shared logic: render lazily, re-render only when the source changes."""

    _attr_content_type = "image/png"

    def __init__(
        self, hass: HomeAssistant, coordinator: VacuulaCoordinator, serial: str
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self.serial = serial
        self._token: str | None = None
        self._png: bytes | None = None

    @property
    def available(self) -> bool:
        # Maps and runs live on the server, so they stay visible while the
        # robot sleeps.
        return self.coordinator.last_update_success and self.serial in (
            self.coordinator.data or {}
        )

    def _current_token(self) -> str | None:
        raise NotImplementedError

    async def _render(self) -> bytes | None:
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        token = self._current_token()
        if token != self._token:
            self._token = token
            self._png = None
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._token = self._current_token()
        self._attr_image_last_updated = dt_util.utcnow()

    async def async_image(self) -> bytes | None:
        if self._png is None and self._token is not None:
            token = self._token
            png = await self._render()
            if token == self._token:  # not superseded while rendering
                self._png = png
            return png
        return self._png


class ActiveMapImage(_MapImage):
    """The floor plan that is active (promoted) on the robot."""

    _attr_translation_key = "map"

    def __init__(self, hass, coordinator, serial) -> None:
        super().__init__(hass, coordinator, serial)
        self._attr_unique_id = f"{serial}_map"

    def _current_token(self) -> str | None:
        active = self.robot.active_map
        return str(active["id"]) if active and "id" in active else None

    async def _render(self) -> bytes | None:
        map_id = self._token
        floor = await self.coordinator.async_fetch_map(self.serial, map_id)
        if floor is None:
            return None
        return await self.hass.async_add_executor_job(render_map, floor, None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        active = self.robot.active_map or {}
        return {"map_name": active.get("name"), "zones": self.robot.zones}


class LastRunImage(_MapImage):
    """The most recent cleaning: floor plan with the driven path on top."""

    _attr_translation_key = "last_run_map"

    def __init__(self, hass, coordinator, serial) -> None:
        super().__init__(hass, coordinator, serial)
        self._attr_unique_id = f"{serial}_last_run_map"

    def _current_token(self) -> str | None:
        run = self.robot.last_run
        return str(run["id"]) if run and run.get("id") else None

    async def _render(self) -> bytes | None:
        run_id = self._token
        run = self.robot.last_run or {}
        floor = await self.coordinator.async_fetch_map(
            self.serial, str(run.get("floorplan") or run_id)
        )
        if floor is None:
            return None
        path = await self.coordinator.async_fetch_run_path(self.serial, run_id)
        return await self.hass.async_add_executor_job(render_map, floor, path)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        run = self.robot.last_run or {}
        return {"area": run.get("area"), "duration": run.get("duration")}
