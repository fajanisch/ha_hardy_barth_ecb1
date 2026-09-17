"""Sensor-Plattform für die Hardy Barth eCB1 Integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfEnergy, UnitOfPower
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

    entities = []

    # Durchlaufe die Meter-Daten (Grid, Wallbox)
    meters = coordinator.data.get("meters", [])
    for meter in meters:
        serial = meter.get("serial")
        name = meter.get("name", "Unknown")
        
        # Leistungssensor (lgwb)
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
        
        # Energiezähler Bezug / Total (1-0:1.8.0)
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

    # Wallbox Steuerungsspezifische Sensoren (chargecontrols)
    charge_controls = coordinator.data.get("chargecontrols", [])
    for cc in charge_controls:
        cc_id = cc.get("id", 1)
        cc_name = cc.get("name", "evcc1")

        # Ladestatus (z.B. A, B, C)
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
        # Aktueller Ladestrom in Ampere
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


def _get_meter_value(data: dict, serial: Any, key: str) -> float | None  :
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