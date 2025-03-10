from homeassistant.helpers.entity import Entity

DOMAIN = "homechum_ev_charging_tracker"

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the EV charging tracking sensors."""
    add_entities([
        VehicleEnergyConsumptionSensor(hass),
        VehicleChargingCostSensor(hass),
        VehicleChargingSavingsSensor(hass),
        PublicChargingEfficiencySensor(hass),
        PublicChargingCostPerMileSensor(hass),
        VehicleTotalEnergyConsumedSensor(hass),
        VehicleTotalChargingCostSensor(hass),
        VehicleOverallEfficiencySensor(hass)
    ])

class VehicleEnergyConsumptionSensor(Entity):
    """Sensor for Miles per kWh."""

    def __init__(self, hass):
        self.hass = hass
        self._state = None

    @property
    def name(self):
        return "Vehicle Miles per kWh"

    @property
    def state(self):
        """Calculate efficiency based on odometer and charger data."""
        miles_now = float(self.hass.states.get("sensor.vehicle_odometer").state or 0)
        miles_last = float(self.hass.states.get("input_number.last_vehicle_odometer").state or 0)
        energy_used = float(self.hass.states.get("sensor.charger_energy_used").state or 0)

        if energy_used > 0:
            self._state = round((miles_now - miles_last) / energy_used, 2)
        else:
            self._state = 0

        return self._state

class VehicleChargingCostSensor(Entity):
    """Sensor for Charging Cost per Session."""

    def __init__(self, hass):
        self.hass = hass
        self._state = None

    @property
    def name(self):
        return "Vehicle Charging Cost"

    @property
    def state(self):
        """Calculate session cost based on charge mode and tariff."""
        energy_used = float(self.hass.states.get("sensor.charger_energy_used").state or 0)
        charge_mode = self.hass.states.get("select.charger_charge_mode").state
        octopus_rate = float(self.hass.states.get("sensor.octopus_electricity_current_rate").state or 0)

        # Use 7p/kWh for Smart Charge mode, else use Octopus dynamic rate
        if charge_mode == "Smart Charge":
            tariff = 0.07  # 7p/kWh
        else:
            tariff = octopus_rate

        self._state = round(energy_used * tariff, 2)

        return self._state

class VehicleChargingSavingsSensor(Entity):
    """Sensor for tracking charging savings based on smart charging usage."""

    def __init__(self, hass):
        self.hass = hass
        self._state = None

    @property
    def name(self):
        return "Vehicle Charging Savings"

    @property
    def state(self):
        """Calculate savings compared to peak rate charging."""
        energy_used = float(self.hass.states.get("sensor.charger_energy_used").state or 0)
        peak_rate = float(self.hass.states.get("sensor.octopus_electricity_current_rate").state or 0)
        charge_mode = self.hass.states.get("select.charger_charge_mode").state

        # If Smart Charge is active, calculate savings
        if charge_mode == "Smart Charge":
            savings = energy_used * (peak_rate - 0.07)  # Compare with 7p/kWh
        else:
            savings = 0  # No savings when using normal rate

        self._state = round(savings, 2)
        return self._state

class PublicChargingEfficiencySensor(Entity):
    """Sensor for Miles per kWh in Public Charging."""

    def __init__(self, hass):
        self.hass = hass
        self._state = None

    @property
    def name(self):
        return "Public Charge Miles per kWh"

    @property
    def state(self):
        """Calculate efficiency based on user input."""
        miles_driven = float(self.hass.states.get("input_number.public_charge_miles").state or 0)
        kwh_used = float(self.hass.states.get("input_number.public_charge_kwh").state or 0)

        if kwh_used > 0:
            self._state = round(miles_driven / kwh_used, 2)
        else:
            self._state = 0

        return self._state

class PublicChargingCostPerMileSensor(Entity):
    """Sensor for Cost per Mile in Public Charging."""

    def __init__(self, hass):
        self.hass = hass
        self._state = None

    @property
    def name(self):
        return "Public Charge Cost per Mile"

    @property
    def state(self):
        """Calculate cost per mile based on user input."""
        cost = float(self.hass.states.get("input_number.public_charge_cost").state or 0)
        miles_driven = float(self.hass.states.get("input_number.public_charge_miles").state or 0)

        if miles_driven > 0:
            self._state = round(cost / miles_driven, 2)
        else:
            self._state = 0

        return self._state

class VehicleTotalEnergyConsumedSensor(Entity):
    """Sensor for Total Energy Consumed (Public + Home Charging)."""

    def __init__(self, hass):
        self.hass = hass
        self._state = None

    @property
    def name(self):
        return "Total Energy Consumed (kWh)"

    @property
    def state(self):
        """Calculate total energy consumption from all charging types."""
        home_energy = float(self.hass.states.get("sensor.charger_energy_used").state or 0)
        public_energy = float(self.hass.states.get("input_number.public_charge_kwh").state or 0)

        self._state = round(home_energy + public_energy, 2)
        return self._state

class VehicleTotalChargingCostSensor(Entity):
    """Sensor for Total Charging Cost (Public + Home Charging)."""

    def __init__(self, hass):
        self.hass = hass
        self._state = None

    @property
    def name(self):
        return "Total Charging Cost (£)"

    @property
    def state(self):
        """Calculate total charging cost across all methods."""
        home_cost = float(self.hass.states.get("sensor.vehicle_charging_cost").state or 0)
        public_cost = float(self.hass.states.get("input_number.public_charge_cost").state or 0)

        self._state = round(home_cost + public_cost, 2)
        return self._state

class VehicleOverallEfficiencySensor(Entity):
    """Sensor for Overall Efficiency (Miles per kWh across all charging types)."""

    def __init__(self, hass):
        self.hass = hass
        self._state = None

    @property
    def name(self):
        return "Overall Efficiency (Miles per kWh)"

    @property
    def state(self):
        """Calculate miles per kWh including home & public charging."""
        total_miles = float(self.hass.states.get("sensor.vehicle_odometer").state or 0)
        last_miles = float(self.hass.states.get("input_number.last_vehicle_odometer").state or 0)
        total_energy = float(self.hass.states.get("sensor.vehicle_total_energy_consumed").state or 0)

        if total_energy > 0:
            self._state = round((total_miles - last_miles) / total_energy, 2)
        else:
            self._state = 0

        return self._state