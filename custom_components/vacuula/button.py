"""Buttons: clean the selected zone, reload runs/maps."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import VacuulaConfigEntry, VacuulaCoordinator
from .entity import VacuulaEntity, async_add_robot_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VacuulaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_robot_entities(
        entry,
        async_add_entities,
        lambda c, s: [CleanZoneButton(c, s), RefreshDataButton(c, s)],
    )


class CleanZoneButton(VacuulaEntity, ButtonEntity):
    """Starts a cleaning of the zone chosen in the zone select."""

    _attr_translation_key = "clean_zone"

    def __init__(self, coordinator: VacuulaCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_clean_zone"

    async def async_press(self) -> None:
        zones = self.robot.zones
        zone = self.coordinator.selected_zone.get(self.serial)
        if zone not in zones:
            zone = zones[0] if zones else None
        if zone is None:
            raise ServiceValidationError(
                "No zones found. Activate a map with zones in the Vacuula app."
            )
        await self.coordinator.async_start_cleaning(self.serial, zones=[zone])


class RefreshDataButton(VacuulaEntity, ButtonEntity):
    """Reload runs, maps, zones and settings right now."""

    _attr_translation_key = "refresh_data"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VacuulaCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_refresh_data"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.serial in (
            self.coordinator.data or {}
        )

    async def async_press(self) -> None:
        await self.coordinator.async_refresh_extras(self.serial)
