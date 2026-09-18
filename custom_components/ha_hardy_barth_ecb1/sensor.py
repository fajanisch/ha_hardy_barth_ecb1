"""Sensor-Plattform für die Hardy Barth eCB1 Integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ECB1DataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet die eCB1 Sensoren ein."""
    coordinator: ECB1DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [ECB1RawDataSensor(coordinator, "all_data")]

    for path, value in _iter_leaf_values(coordinator.data):
        if value is None:
            continue
        unit, device_class, state_class = _infer_sensor_metadata(path, value)
        entities.append(
            ECB1GeneratedSensor(
                coordinator,
                path,
                value,
                unit,
                device_class,
                state_class,
            )
        )

    meters = coordinator.data.get("meters", [])
    for meter in meters:
        serial = meter.get("serial")
        name = meter.get("name", "Unknown")

        entities.append(
            ECB1MeterSensor(
                coordinator,
                serial,
                name,
                "power",
                "Leistung",
                UnitOfPower.WATT,
                SensorDeviceClass.POWER,
                SensorStateClass.MEASUREMENT,
                lambda data, s_id=serial: _get_meter_value(data, s_id, "lgwb"),
            )
        )

        entities.append(
            ECB1MeterSensor(
                coordinator,
                serial,
                name,
                "energy_in",
                "Energie Gesamt",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL_INCREASING,
                lambda data, s_id=serial: _get_meter_value(data, s_id, "1-0:1.8.0"),
            )
        )

    charge_controls = coordinator.data.get("chargecontrols", [])
    for cc in charge_controls:
        cc_id = cc.get("id", 1)
        cc_name = cc.get("name", "evcc1")

        entities.append(
            ECB1ControlSensor(
                coordinator,
                cc_id,
                cc_name,
                "state",
                "Ladestatus",
                None,
                None,
                None,
                lambda data, c_id=cc_id: _get_cc_value(data, c_id, "state"),
            )
        )
        entities.append(
            ECB1ControlSensor(
                coordinator,
                cc_id,
                cc_name,
                "currentpwmamp",
                "Ladestrom Soll",
                UnitOfElectricCurrent.AMPERE,
                SensorDeviceClass.CURRENT,
                SensorStateClass.MEASUREMENT,
                lambda data, c_id=cc_id: _get_cc_value(data, c_id, "currentpwmamp"),
            )
        )

    async_add_entities(entities)


def _iter_leaf_values(data: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    """Return all scalar values as path tuples for dynamic sensor creation."""
    items: list[tuple[tuple[str, ...], Any]] = []

    if isinstance(data, dict):
        for key, value in data.items():
            next_path = path + (str(key),)
            if isinstance(value, (dict, list)):
                items.extend(_iter_leaf_values(value, next_path))
            elif value is not None:
                items.append((next_path, value))
    elif isinstance(data, list):
        for index, item in enumerate(data):
            next_path = path + (str(index),)
            if isinstance(item, (dict, list)):
                items.extend(_iter_leaf_values(item, next_path))
            elif item is not None:
                items.append((next_path, item))
    else:
        if data is not None:
            items.append((path, data))

    return items


def _get_nested_value(data: Any, path: tuple[str, ...]) -> Any:
    """Fetch the value identified by a nested path tuple."""
    current = data
    for part in path:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError, TypeError):
                return None
        else:
            return None
    return current


def _clean_key_name(value: str) -> str:
    """Normalize a field name for cleaner UI labels."""
    cleaned = str(value).replace("_", " ").replace("-", " ")
    cleaned = " ".join(part.capitalize() if part.isalpha() else part for part in cleaned.split())
    return cleaned.strip()


def _format_path_name(path: tuple[str, ...]) -> str:
    """Create a readable human name from a nested path."""
    parts = [
        _clean_key_name(part)
        for part in path
        if str(part) not in {"", "None"}
    ]
    if not parts:
        return "Value"
    return " ".join(parts)


def _infer_sensor_metadata(path: tuple[str, ...], value: Any) -> tuple[str | None, SensorDeviceClass | None, SensorStateClass | None]:
    """Infer units and metadata for a sensor based on its path and value."""
    lowered = "_".join(str(part).lower() for part in path)

    if "energy" in lowered or "kwh" in lowered or "total" in lowered and "import" in lowered:
        return UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING
    if "power" in lowered or "lgwb" in lowered:
        return UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT
    if "current" in lowered or "amp" in lowered:
        return UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT
    if "voltage" in lowered or "volt" in lowered:
        return UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT
    if "temp" in lowered or "temperature" in lowered:
        return UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT

    if isinstance(value, (int, float)):
        return None, None, SensorStateClass.MEASUREMENT

    return None, None, None


def _get_meter_value(data: dict, serial: Any, key: str) -> float | None:
    """Hilfsfunktion zum Extrahieren von Meter-Werten anhand der Seriennummer."""
    for meter in data.get("meters", []):
        if str(meter.get("serial")) == str(serial):
            if key == "lgwb":
                val = meter.get("lgwb")
                return float(val) if val is not None else None
            return meter.get("data", {}).get(key)
    return None


def _get_cc_value(data: dict, cc_id: int, key: str) -> Any:
    """Hilfsfunktion zum Extrahieren von Chargecontrol-Werten."""
    for cc in data.get("chargecontrols", []):
        if cc.get("id") == cc_id:
            return cc.get(key)
    return None


class ECB1GeneratedSensor(CoordinatorEntity, SensorEntity):
    """Represents an arbitrary scalar value returned by the eCB1 API."""

    def __init__(
        self,
        coordinator: ECB1DataUpdateCoordinator,
        path: tuple[str, ...],
        value: Any,
        unit: str | None,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._path = path
        self._value_source = lambda data, p=path: _get_nested_value(data, p)
        safe_path = "_".join(str(part) for part in path)
        self._attr_unique_id = f"ecb1_{safe_path}"
        self._attr_name = f"eCB1 {_format_path_name(path)}"
        self._attr_has_entity_name = True
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        return self._value_source(self.coordinator.data)


class ECB1RawDataSensor(CoordinatorEntity, SensorEntity):
    """Expose the complete eCB1 API payload as sensor attributes."""

    def __init__(self, coordinator: ECB1DataUpdateCoordinator, sensor_type: str) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_unique_id = f"ecb1_{sensor_type}"
        self._attr_name = "eCB1 Raw Data"

    @property
    def native_value(self) -> int:
        """Return a simple state value so the entity is visible in the UI."""
        return len(self.coordinator.data) if self.coordinator.data else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the full API payload as entity attributes."""
        return self.coordinator.data or {}


class ECB1MeterSensor(CoordinatorEntity, SensorEntity):
    """Repräsentiert einen Zähler- oder Leistungssensor der eCB1."""

    def __init__(
        self,
        coordinator: ECB1DataUpdateCoordinator,
        serial: Any,
        meter_name: str,
        sensor_type: str,
        name_suffix: str,
        unit: str | None,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        value_fn,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._serial = serial
        self._sensor_type = sensor_type
        self._value_fn = value_fn
        
        self._attr_unique_id = f"ecb1_{serial}_{sensor_type}"
        self._attr_name = f"eCB1 {meter_name} {name_suffix}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def native_value(self) -> Any:
        """Gibt den aktuellen Wert zurück."""
        return self._value_fn(self.coordinator.data)


class ECB1ControlSensor(CoordinatorEntity, SensorEntity):
    """Repräsentiert einen Steuerungs-Sensor der Wallbox (z.B. Ladestatus)."""

    def __init__(
        self,
        coordinator: ECB1DataUpdateCoordinator,
        cc_id: int,
        cc_name: str,
        sensor_type: str,
        name_suffix: str,
        unit: str | None,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        value_fn,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._cc_id = cc_id
        self._sensor_type = sensor_type
        self._value_fn = value_fn
        
        self._attr_unique_id = f"ecb1_cc_{cc_id}_{sensor_type}"
        self._attr_name = f"eCB1 {cc_name} {name_suffix}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def native_value(self) -> Any:
        """Gibt den aktuellen Wert zurück."""
        return self._value_fn(self.coordinator.data)