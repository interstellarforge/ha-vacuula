"""Switches for robot settings."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import VacuulaConfigEntry, VacuulaCoordinator
from .entity import VacuulaEntity, async_add_robot_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VacuulaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_robot_entities(
        entry, async_add_entities, lambda c, s: [ForceFloorplanSwitch(c, s)]
    )


class ForceFloorplanSwitch(VacuulaEntity, SwitchEntity):
    """settings.cleaning_options -> force_floorplan."""

    _attr_translation_key = "force_floorplan"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: VacuulaCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_force_floorplan"

    @property
    def is_on(self) -> bool | None:
        return self.robot.force_floorplan

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_force_floorplan(self.serial, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_force_floorplan(self.serial, False)
