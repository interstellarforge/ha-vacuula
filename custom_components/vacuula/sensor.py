"""Sensors for Vacuula robots."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ACTIONS
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
        lambda c, s: [BatterySensor(c, s), ActionSensor(c, s), ErrorSensor(c, s)],
    )


class BatterySensor(VacuulaEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: VacuulaCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_battery"

    @property
    def native_value(self) -> int | None:
        charge = self.robot.details.get("charge")
        return int(charge) if charge is not None else None


class ActionSensor(VacuulaEntity, SensorEntity):
    _attr_translation_key = "action"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ACTIONS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VacuulaCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_action"

    @property
    def native_value(self) -> str | None:
        return self.robot.action if self.robot.action in ACTIONS else None


class ErrorSensor(VacuulaEntity, SensorEntity):
    _attr_translation_key = "error"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VacuulaCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_error"

    @property
    def native_value(self) -> str:
        errors = self.robot.errors
        return ", ".join(str(e.get("code")) for e in errors) if errors else "none"

    @property
    def extra_state_attributes(self) -> dict:
        return {"errors": self.robot.errors}
