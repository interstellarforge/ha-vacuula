"""Sensors for Vacuula robots."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfArea, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ACTIONS
from .coordinator import RobotData, VacuulaConfigEntry, VacuulaCoordinator
from .entity import VacuulaEntity, async_add_robot_entities
from .runs import to_json


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VacuulaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_robot_entities(
        entry,
        async_add_entities,
        lambda c, s: [
            BatterySensor(c, s),
            ActionSensor(c, s),
            ErrorSensor(c, s),
            *(RunSensor(c, s, description) for description in RUN_SENSORS),
        ],
    )


@dataclass(frozen=True, kw_only=True)
class VacuulaSensorDescription(SensorEntityDescription):
    value_fn: Callable[[RobotData], Any]


def _last(key: str) -> Callable[[RobotData], Any]:
    return lambda robot: (robot.last_run or {}).get(key)


def _total_area(robot: RobotData) -> float | None:
    areas = [r["area"] for r in robot.runs if r.get("area") is not None]
    return round(sum(areas), 1) if areas else None


RUN_SENSORS: tuple[VacuulaSensorDescription, ...] = (
    VacuulaSensorDescription(
        key="last_run_area",
        translation_key="last_run_area",
        device_class=SensorDeviceClass.AREA,
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_last("area"),
    ),
    VacuulaSensorDescription(
        key="last_run_duration",
        translation_key="last_run_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_last("duration"),
    ),
    VacuulaSensorDescription(
        key="last_run_battery_used",
        translation_key="last_run_battery_used",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_last("battery_consumed"),
    ),
    VacuulaSensorDescription(
        key="last_run_end",
        translation_key="last_run_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_last("end"),
    ),
    VacuulaSensorDescription(
        key="last_run_started_by",
        translation_key="last_run_started_by",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_last("started_by"),
    ),
    VacuulaSensorDescription(
        key="run_count",
        translation_key="run_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda robot: len(robot.runs),
    ),
    VacuulaSensorDescription(
        key="total_area",
        translation_key="total_area",
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        state_class=SensorStateClass.TOTAL,
        value_fn=_total_area,
    ),
)


class RunSensor(VacuulaEntity, SensorEntity):
    """Statistics from the runs stored on the Vacuula server."""

    entity_description: VacuulaSensorDescription

    def __init__(
        self,
        coordinator: VacuulaCoordinator,
        serial: str,
        description: VacuulaSensorDescription,
    ) -> None:
        super().__init__(coordinator, serial)
        self.entity_description = description
        self._attr_unique_id = f"{serial}_{description.key}"

    @property
    def available(self) -> bool:
        # Runs live on the server and stay readable while the robot sleeps.
        return self.coordinator.last_update_success and self.serial in (
            self.coordinator.data or {}
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.robot)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key != "last_run_area":
            return None
        run = self.robot.last_run
        return {
            "run": to_json(run) if run else None,
            "recent_runs": [to_json(r) for r in self.robot.runs[:10]],
        }


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

    @property
    def extra_state_attributes(self) -> dict:
        return {"autonomy_states": self.robot.autonomy_states}


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
