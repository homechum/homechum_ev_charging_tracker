from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ENERGY_KILO_WATT_HOUR, CURRENCY_POUND
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "homechum_ev_charging_tracker"

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the EV charging tracking sensors."""
    async_add_entities([
        VehicleEnergyConsumptionSensor(hass),
        VehicleChargingCostSensor(hass),
        VehicleChargingSavingsSensor(hass),
        PublicChargingEfficiencySensor(hass),
        PublicChargingCostPerMileSensor(hass),
        VehicleTotalEnergyConsumedSensor(hass),
        VehicleTotalChargingCostSensor(hass),
        VehicleOverallEfficiencySensor(hass)
    ])

class BaseEVSensor(SensorEntity):
    """Base class for EV sensors to handle error handling and state fetching."""
    
    def __init__(self, hass, name, unit, icon):
        """Initialize the sensor."""
        self.hass = hass
        self._state = None
        self._attr_name = name
        self._attr_unit_of_measurement = unit
        self._attr_icon = icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def get_state(self, entity_id, default=0.0):
        """Helper function to fetch sensor states safely."""
        try:
            state = self.hass.states.get(entity_id)
            return float(state.state) if state and state.state not in ["unknown", "unavailable"] else default
        except (ValueError, TypeError):
            return default

# ---- Charging Efficiency ----
class VehicleEnergyConsumptionSensor(BaseEVSensor):
    """Sensor for Miles per kWh."""

    def __init__(self, hass):
        super().__init__(hass, "Vehicle Miles per kWh", "mi/kWh", "mdi:car-speedometer")

    def update(self):
        miles_now = self.get_state("sensor.vehicle_odometer")
        miles_last = self.get_state("input_number.last_vehicle_odometer")
        energy_used = self.get_state("sensor.charger_energy_used")

        self._state = round((miles_now - miles_last) / energy_used, 2) if energy_used > 0 else 0

# ---- Charging Cost Calculation ----
class VehicleChargingCostSensor(BaseEVSensor):
    """Sensor for Charging Cost per Session."""

    def __init__(self, hass):
        super().__init__(hass, "Vehicle Charging Cost", CURRENCY_POUND, "mdi:currency-gbp")

    def update(self):
        energy_used = self.get_state("sensor.charger_energy_used")
        charge_mode = self.hass.states.get("select.charger_charge_mode").state
        octopus_rate = self.get_state("sensor.octopus_electricity_current_rate")

        # Use 7p/kWh for Smart Charge mode, else use Octopus dynamic rate
        tariff = 0.07 if charge_mode == "Smart Charge" else octopus_rate
        self._state = round(energy_used * tariff, 2)

# ---- Charging Savings Calculation ----
class VehicleChargingSavingsSensor(BaseEVSensor):
    """Sensor for tracking charging savings based on smart charging usage."""

    def __init__(self, hass):
        super().__init__(hass, "Vehicle Charging Savings", CURRENCY_POUND, "mdi:currency-usd")

    def update(self):
        energy_used = self.get_state("sensor.charger_energy_used")
        peak_rate = self.get_state("sensor.octopus_electricity_current_rate")
        charge_mode = self.hass.states.get("select.charger_charge_mode").state

        self._state = round(energy_used * (peak_rate - 0.07), 2) if charge_mode == "Smart Charge" else 0

# ---- Public Charging Efficiency ----
class PublicChargingEfficiencySensor(BaseEVSensor):
    """Sensor for Miles per kWh in Public Charging."""

    def __init__(self, hass):
        super().__init__(hass, "Public Charge Miles per kWh", "mi/kWh", "mdi:ev-station")

    def update(self):
        miles_driven = self.get_state("input_number.public_charge_miles")
        kwh_used = self.get_state("input_number.public_charge_kwh")

        self._state = round(miles_driven / kwh_used, 2) if kwh_used > 0 else 0

# ---- Public Charging Cost per Mile ----
class PublicChargingCostPerMileSensor(BaseEVSensor):
    """Sensor for Cost per Mile in Public Charging."""

    def __init__(self, hass):
        super().__init__(hass, "Public Charge Cost per Mile", CURRENCY_POUND, "mdi:ev-station")

    def update(self):
        cost = self.get_state("input_number.public_charge_cost")
        miles_driven = self.get_state("input_number.public_charge_miles")

        self._state = round(cost / miles_driven, 2) if miles_driven > 0 else 0

# ---- Total Energy Consumption ----
class VehicleTotalEnergyConsumedSensor(BaseEVSensor):
    """Sensor for Total Energy Consumed (Public + Home Charging)."""

    def __init__(self, hass):
        super().__init__(hass, "Total Energy Consumed", ENERGY_KILO_WATT_HOUR, "mdi:lightning-bolt")

    def update(self):
        home_energy = self.get_state("sensor.charger_energy_used")
        public_energy = self.get_state("input_number.public_charge_kwh")

        self._state = round(home_energy + public_energy, 2)

# ---- Total Charging Cost ----
class VehicleTotalChargingCostSensor(BaseEVSensor):
    """Sensor for Total Charging Cost (Public + Home Charging)."""

    def __init__(self, hass):
        super().__init__(hass, "Total Charging Cost", CURRENCY_POUND, "mdi:currency-gbp")

    def update(self):
        home_cost = self.get_state("sensor.vehicle_charging_cost")
        public_cost = self.get_state("input_number.public_charge_cost")

        self._state = round(home_cost + public_cost, 2)

# ---- Overall Efficiency ----
class VehicleOverallEfficiencySensor(BaseEVSensor):
    """Sensor for Overall Efficiency (Miles per kWh across all charging types)."""

    def __init__(self, hass):
        super().__init__(hass, "Overall Efficiency", "mi/kWh", "mdi:car-speedometer")

    def update(self):
        total_miles = self.get_state("sensor.vehicle_odometer")
        last_miles = self.get_state("input_number.last_vehicle_odometer")
        total_energy = self.get_state("sensor.vehicle_total_energy_consumed")

        self._state = round((total_miles - last_miles) / total_energy, 2) if total_energy > 0 else 0