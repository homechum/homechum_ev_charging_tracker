"""Sensor platform for HomeChum EV Charging Tracker."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

def get_float_state(hass: HomeAssistant, entity_id: str, default: float = 0.0) -> float:
    """Helper to safely get a float value from an entity state."""
    state_obj = hass.states.get(entity_id)
    if state_obj is None or state_obj.state in ["unknown", "unavailable"]:
        return default
    try:
        return float(state_obj.state)
    except (ValueError, TypeError):
        return default

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensor entities from a config entry."""
    sensors = [
        MilesPerSocSensor(hass),
        MilesPerKwhSensor(hass),
        ChargingCostPerKwhSensor(hass),
        ChargingCostSessionSensor(hass),
        OptimalChargingCostSensor(hass),
        SavingsPerChargeSensor(hass),
        PublicChargingAvgCostPerKwhSensor(hass),
        PublicChargingAvgEfficiencySensor(hass),
    ]
    async_add_entities(sensors)

class MilesPerSocSensor(SensorEntity):
    """Sensor: Miles per 1% State of Charge during discharge.

    This sensor computes the efficiency in terms of miles per percentage point of SOC consumed.
    If the vehicle is charging or idle (SOC is increasing or unchanged), it returns the previous computed value.
    """
    _attr_name = "MyIDA Miles per 1% SoC"
    _attr_unit_of_measurement = "mi/%"

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._last_value = None  # Cache the last computed value

    @property
    def state(self):
        miles_now = get_float_state(self.hass, "sensor.myida_odometer")
        soc_now = get_float_state(self.hass, "sensor.myida_battery_level")
        miles_last = get_float_state(self.hass, "input_number.myida_start_mile")
        soc_last = get_float_state(self.hass, "input_number.myida_start_soc")
        
        # If SOC is not decreasing, assume the vehicle is charging or idle.
        # Return the previous value if available.
        if soc_now >= soc_last:
            return self._last_value if self._last_value is not None else 0
        
        soc_used = soc_last - soc_now
        if soc_used > 0:
            calculated_value = round((miles_now - miles_last) / soc_used, 2)
            self._last_value = calculated_value  # Update the cache
            return calculated_value
        
        return self._last_value if self._last_value is not None else 0

class MilesPerKwhSensor(SensorEntity):
    """Sensor: Miles per kWh charged."""
    _attr_name = "MyIDA Miles per kWh"
    _attr_unit_of_measurement = "mi/kWh"

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    @property
    def state(self):
        miles_now = get_float_state(self.hass, "sensor.myida_odometer")
        miles_last = get_float_state(self.hass, "input_number.myida_start_mile")
        energy_used = get_float_state(self.hass, "sensor.ohme_epod_energy")
        if energy_used > 0:
            return round((miles_now - miles_last) / energy_used, 2)
        return 0

class ChargingCostPerKwhSensor(SensorEntity):
    """Sensor: Charging cost per kWh based on charging mode."""
    _attr_name = "MyIDA Charging Cost per kWh"
    _attr_unit_of_measurement = "£/kWh"

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    @property
    def state(self):
        charge_mode = self.hass.states.get("select.ohme_epod_charge_mode")
        if charge_mode and charge_mode.state == "smart_charge":
            return 0.07
        return get_float_state(self.hass, "sensor.octopus_electricity_current_rate")

class ChargingCostSessionSensor(SensorEntity):
    """Sensor: Total cost of the current charging session."""
    _attr_name = "MyIDA Charging Cost Per Session"
    _attr_unit_of_measurement = "£"

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    @property
    def state(self):
        energy_used = get_float_state(self.hass, "sensor.ohme_epod_energy")
        charge_mode = self.hass.states.get("select.ohme_epod_charge_mode")
        if charge_mode and charge_mode.state == "smart_charge":
            cost_per_kwh = 0.07
        else:
            cost_per_kwh = get_float_state(self.hass, "sensor.octopus_electricity_current_rate")
        return round(energy_used * cost_per_kwh, 2)

class OptimalChargingCostSensor(SensorEntity):
    """Sensor: Optimal charging cost per kWh (either smart or tariff based)."""
    _attr_name = "MyIDA Optimal Charging Cost"
    _attr_unit_of_measurement = "£/kWh"

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    @property
    def state(self):
        charge_mode = self.hass.states.get("select.ohme_epod_charge_mode")
        if charge_mode and charge_mode.state == "smart_charge":
            return 0.07
        return get_float_state(self.hass, "sensor.octopus_electricity_current_rate")

class SavingsPerChargeSensor(SensorEntity):
    """Sensor: Potential savings per charging session."""
    _attr_name = "MyIDA Savings Per Charge"
    _attr_unit_of_measurement = "£"

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    @property
    def state(self):
        energy_used = get_float_state(self.hass, "sensor.ohme_epod_energy")
        current_rate = get_float_state(self.hass, "sensor.octopus_electricity_current_rate")
        charge_mode = self.hass.states.get("select.ohme_epod_charge_mode")
        if charge_mode and charge_mode.state == "smart_charge":
            optimal_rate = 0.07
        else:
            optimal_rate = current_rate
        if energy_used > 0 and current_rate >= optimal_rate:
            return round(energy_used * (current_rate - optimal_rate), 2)
        return 0

# ---------------------------------------------------------------------------
# New Sensors: Based on stored manual input from public charging sessions
# ---------------------------------------------------------------------------

class PublicChargingAvgCostPerKwhSensor(SensorEntity):
    """Sensor: Average cost per kWh across all manual public charging sessions."""
    _attr_name = "Public Charging Avg Cost per kWh"
    _attr_unit_of_measurement = "£/kWh"

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    @property
    def state(self):
        data = self.hass.data.get(DOMAIN, {}).get("public_sessions", {})
        sessions = data.get("sessions", [])
        if not sessions:
            return 0
        total_kwh = 0
        total_cost = 0
        for session in sessions:
            try:
                kwh = float(session.get("kwh", 0))
                cost = float(session.get("cost", 0))
            except ValueError:
                continue
            total_kwh += kwh
            total_cost += cost
        if total_kwh > 0:
            return round(total_cost / total_kwh, 2)
        return 0

class PublicChargingAvgEfficiencySensor(SensorEntity):
    """Sensor: Average miles per kWh (efficiency) across manual public charging sessions."""
    _attr_name = "Public Charging Avg Efficiency"
    _attr_unit_of_measurement = "mi/kWh"

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    @property
    def state(self):
        data = self.hass.data.get(DOMAIN, {}).get("public_sessions", {})
        sessions = data.get("sessions", [])
        if not sessions:
            return 0
        total_kwh = 0
        total_miles = 0
        for session in sessions:
            try:
                kwh = float(session.get("kwh", 0))
                miles = float(session.get("miles", 0))
            except ValueError:
                continue
            total_kwh += kwh
            total_miles += miles
        if total_kwh > 0:
            return round(total_miles / total_kwh, 2)
        return 0