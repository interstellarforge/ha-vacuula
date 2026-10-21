"""Select entities: cleaning and navigation mode used when starting a clean."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CLEANING_MODES, NAVIGATION_MODES
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
        lambda c, s: [
            ModeSelect(c, s, "cleaning_mode", "mode", CLEANING_MODES),
            ModeSelect(c, s, "navigation_mode", "navigation_mode", NAVIGATION_MODES),
        ],
    )


class ModeSelect(VacuulaEntity, SelectEntity, RestoreEntity):
    """The robot does not report these, so they are remembered by Home Assistant."""

    def __init__(
        self,
        coordinator: VacuulaCoordinator,
        serial: str,
        key: str,
        setting: str,
        options: list[str],
    ) -> None:
        super().__init__(coordinator, serial)
        self._setting = setting
        self._attr_translation_key = key
        self._attr_options = options
        self._attr_unique_id = f"{serial}_{key}"

    @property
    def available(self) -> bool:
        # Pure Home Assistant settings: usable even while the robot sleeps.
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in self._attr_options:
            self.coordinator.cleaning_settings[self.serial][self._setting] = last.state

    @property
    def current_option(self) -> str:
        return self.coordinator.cleaning_settings[self.serial][self._setting]

    async def async_select_option(self, option: str) -> None:
        self.coordinator.cleaning_settings[self.serial][self._setting] = option
        self.async_write_ha_state()
