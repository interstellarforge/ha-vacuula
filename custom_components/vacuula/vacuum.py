"""Vacuum entity for Neato Gen4 robots (D8/D9/D10) through Vacuula."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ABILITY_CANCEL,
    ABILITY_FIND_ME,
    ABILITY_PAUSE,
    ABILITY_RESUME,
    ABILITY_RETURN,
    CLEANING_MODES,
    NAVIGATION_MODES,
    SERVICE_CLEAN_ZONES,
    SERVICE_GET_ZONES,
)
from .coordinator import RobotData, VacuulaConfigEntry, VacuulaCoordinator
from .entity import VacuulaEntity, async_add_robot_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VacuulaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_robot_entities(
        entry, async_add_entities, lambda c, s: [VacuulaVacuum(c, s)]
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_CLEAN_ZONES,
        {
            vol.Required("zones"): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional("map"): cv.string,
            vol.Optional("mode"): vol.In(CLEANING_MODES),
            vol.Optional("navigation_mode"): vol.In(NAVIGATION_MODES),
            vol.Optional("nogo_enabled", default=True): cv.boolean,
        },
        "async_clean_zones",
    )
    platform.async_register_entity_service(
        SERVICE_GET_ZONES,
        {vol.Optional("map"): cv.string},
        "async_get_zones",
        supports_response=SupportsResponse.ONLY,
    )


def activity_for(robot: RobotData) -> VacuumActivity:
    """Translate the robot's state/action pair into a vacuum activity."""
    severe = any(
        e.get("severity") in ("error", "critical") for e in robot.errors
    )
    if robot.state == "error" or severe:
        return VacuumActivity.ERROR
    if robot.state == "paused":
        return VacuumActivity.PAUSED
    if robot.action == "cleaning":
        return VacuumActivity.CLEANING
    if robot.action == "docking":
        return VacuumActivity.RETURNING
    if robot.details.get("is_docked"):
        return VacuumActivity.DOCKED
    return VacuumActivity.IDLE


class VacuulaVacuum(VacuulaEntity, StateVacuumEntity):
    """The robot itself."""

    _attr_name = None
    _attr_supported_features = (
        VacuumEntityFeature.START
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.SEND_COMMAND
    )

    def __init__(self, coordinator: VacuulaCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = serial

    @property
    def activity(self) -> VacuumActivity | None:
        return activity_for(self.robot)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        robot = self.robot
        return {
            "robot_state": robot.state,
            "robot_action": robot.action,
            "errors": robot.errors,
            "available_commands": robot.available_commands,
        }

    async def async_start(self) -> None:
        if self.robot.state == "paused":
            await self.coordinator.async_command(self.serial, {"ability": ABILITY_RESUME})
        else:
            await self.coordinator.async_start_cleaning(self.serial)

    async def async_pause(self) -> None:
        await self.coordinator.async_command(self.serial, {"ability": ABILITY_PAUSE})

    async def async_stop(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(self.serial, {"ability": ABILITY_CANCEL})

    async def async_return_to_base(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(self.serial, {"ability": ABILITY_RETURN})

    async def async_locate(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(
            self.serial, {"ability": ABILITY_FIND_ME}, refresh=False
        )

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a raw robot ability, e.g. command='cleaning.pause'."""
        payload: dict[str, Any] = {"ability": command}
        if isinstance(params, dict):
            payload.update(params)
        await self.coordinator.async_command(self.serial, payload)

    async def async_clean_zones(
        self,
        zones: list[str],
        map: str | None = None,  # noqa: A002 - matches the service field name
        mode: str | None = None,
        navigation_mode: str | None = None,
        nogo_enabled: bool = True,
    ) -> None:
        await self.coordinator.async_start_cleaning(
            self.serial,
            map_ref=map,
            zones=zones,
            mode=mode,
            navigation_mode=navigation_mode,
            nogo_enabled=nogo_enabled,
        )

    async def async_get_zones(self, map: str | None = None) -> dict[str, Any]:  # noqa: A002
        return await self.coordinator.async_get_zones(self.serial, map)
