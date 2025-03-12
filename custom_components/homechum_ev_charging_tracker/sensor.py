"""Sensor platform for HomeChum EV Charging Tracker."""
import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant

DOMAIN = "homechum_ev_charging_tracker"

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    """Set up the component via configuration.yaml."""
    hass.helpers.discovery.load_platform("sensor", DOMAIN, {}, config)
    return True

def get_float_state(hass: HomeAssistant, entity_id: str, default: float = 0.0) -> float:
    """Helper to safely get a float value from an entity state."""
    state_obj = hass.states.get(entity_id)
    if state_obj is None or state_obj.state in ["unknown", "unavailable"]:
        return default
    try:
        return float(state_obj.state)
    except (ValueError, TypeError):
        return default

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up sensor entities from a config entry."""
    _LOGGER.debug("Initializing HomeChum EV Charging Tracker sensors...")
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
    _LOGGER.debug(f"Adding sensors: {sensors}")  # Log sensor instances
    async_add_entities(sensors, update_before_add=True)

class MilesPerSocSensor(SensorEntity):
    """Sensor: Miles per 1% State of Charge during discharge.

    This sensor computes the efficiency in terms of miles per percentage point of SOC consumed.
    If the vehicle is charging or idle (SOC is increasing or unchanged), it returns the previous computed value.
    """

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Miles per 1% SoC"
        self._attr_unique_id = "ev_miles_per_soc"
        self._attr_unit_of_measurement = "mi/%"
        self._attr_state = None  # Ensure state starts as None
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

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Miles per kWh"
        self._attr_unique_id = "ev_miles_per_kwh"
        self._attr_unit_of_measurement = "mi/kWh"
        self._attr_state = None

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

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Charging Cost per kWh"
        self._attr_unique_id = "ev_charging_cost_per_kwh"
        self._attr_unit_of_measurement = "£/kWh"
        self._attr_state = None

    @property
    def state(self):
        charge_mode = self.hass.states.get("select.ohme_epod_charge_mode")
        if charge_mode and charge_mode.state == "smart_charge":
            return 0.07
        return get_float_state(self.hass, "sensor.octopus_electricity_current_rate")

class ChargingCostSessionSensor(SensorEntity):
    """Sensor: Total cost of the current charging session."""
    
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Charging Cost Per Session"
        self._attr_unique_id = "ev_charging_cost_session"
        self._attr_unit_of_measurement = "£"
        self._attr_state = None

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

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Optimal Charging Cost"
        self._attr_unit_of_measurement = "£/kWh"
        self._attr_unique_id = "ev_optimal_charging_cost"
        self._attr_state = None

    @property
    def state(self):
        charge_mode = self.hass.states.get("select.ohme_epod_charge_mode")
        if charge_mode and charge_mode.state == "smart_charge":
            return 0.07
        return get_float_state(self.hass, "sensor.octopus_electricity_current_rate")

class SavingsPerChargeSensor(SensorEntity):
    """Sensor: Potential savings per charging session."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Savings Per Charge"
        self._attr_unit_of_measurement = "£"
        self._attr_unique_id = "ev_savings_per_charge"
        self._attr_state = None

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

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Public Charging Avg Cost per kWh"
        self._attr_unit_of_measurement = "£/kWh"
        self._attr_unique_id = "ev_public_charging_avg_cost_per_kwh"
        self._attr_state = None

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

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Public Charging Avg Efficiency"
        self._attr_unit_of_measurement = "mi/kWh"
        self._attr_unique_id = "ev_public_charging_efficiency"
        self._attr_state = None

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
