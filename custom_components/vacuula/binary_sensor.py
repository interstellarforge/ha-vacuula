"""Binary sensors for Vacuula robots."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
        entry,
        async_add_entities,
        lambda c, s: [ChargingSensor(c, s), DockedSensor(c, s), ConnectedSensor(c, s)],
    )


class ChargingSensor(VacuulaEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, coordinator: VacuulaCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_charging"

    @property
    def is_on(self) -> bool | None:
        value = self.robot.details.get("is_charging")
        return None if value is None else bool(value)


class DockedSensor(VacuulaEntity, BinarySensorEntity):
    _attr_translation_key = "docked"

    def __init__(self, coordinator: VacuulaCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_docked"

    @property
    def is_on(self) -> bool | None:
        value = self.robot.details.get("is_docked")
        return None if value is None else bool(value)


class ConnectedSensor(VacuulaEntity, BinarySensorEntity):
    """Whether the robot is connected to the Vacuula server (always available)."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VacuulaCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_connected"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.serial in (
            self.coordinator.data or {}
        )

    @property
    def is_on(self) -> bool:
        return self.robot.connected
