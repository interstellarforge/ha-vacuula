"""Shared entity helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RobotData, VacuulaConfigEntry, VacuulaCoordinator


class VacuulaEntity(CoordinatorEntity[VacuulaCoordinator]):
    """Base class: one entity belongs to one robot (device)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VacuulaCoordinator, serial: str) -> None:
        super().__init__(coordinator)
        self.serial = serial

    @property
    def robot(self) -> RobotData:
        return self.coordinator.data[self.serial]

    @property
    def device_info(self) -> DeviceInfo:
        robot = self.robot
        return DeviceInfo(
            identifiers={(DOMAIN, self.serial)},
            name=robot.name,
            manufacturer="Neato Robotics",
            model="Neato D8/D9/D10 (Gen4)",
            serial_number=robot.label_serial,
            configuration_url=f"http://{self.coordinator.client.host}:{self.coordinator.client.port}/web",
        )

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.serial in (self.coordinator.data or {})
            and self.robot.connected
        )


@callback
def async_add_robot_entities(
    entry: VacuulaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    factory: Callable[[VacuulaCoordinator, str], Iterable[Entity]],
) -> None:
    """Add entities for every robot now, and for robots that show up later."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new = [s for s in (coordinator.data or {}) if s not in known]
        if new:
            known.update(new)
            async_add_entities(
                [entity for serial in new for entity in factory(coordinator, serial)]
            )

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))
