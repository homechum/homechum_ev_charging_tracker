from homeassistant.components.binary_sensor import BinarySensorEntity

class VehicleChargingFailureSensor(BinarySensorEntity):
    """Binary sensor to detect charging failures."""

    def __init__(self, hass):
        self.hass = hass
        self._state = False

    @property
    def name(self):
        return "Vehicle EV Charging Failure Detected"

    @property
    def is_on(self):
        """Detect charging failure if charger is active but no power is drawn."""
        charger_status = self.hass.states.get("sensor.ohme_epod_status").state
        charger_power = float(self.hass.states.get("sensor.ohme_epod_power").state or 0)

        self._state = charger_status == "charging" and charger_power == 0
        return self._state
    
class VehiclePublicChargingDetectionSensor(BinarySensorEntity):
    """Binary sensor to detect when the vehicle is charging outside home."""

    def __init__(self, hass):
        self.hass = hass
        self._state = False

    @property
    def name(self):
        return "VW EV Public Charging Detected"

    @property
    def is_on(self):
        """Detect public charging when the vehicle is plugged in but Ohme charger is inactive."""
        car_plugged_in = self.hass.states.get("binary_sensor.myida_charging_cable_connected").state
        home_charger_active = self.hass.states.get("binary_sensor.ohme_active").state

        self._state = car_plugged_in == "on" and home_charger_active == "off"
        return self._state