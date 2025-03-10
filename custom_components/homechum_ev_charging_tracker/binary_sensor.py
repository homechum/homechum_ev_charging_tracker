from homeassistant.components.binary_sensor import BinarySensorEntity

DOMAIN = "homechum_ev_charging_tracker"

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the EV Charging binary sensors."""
    async_add_entities([
        ChargingFailureSensor(hass),
        PublicChargingDetectionSensor(hass)
    ])

class BaseEVBinarySensor(BinarySensorEntity):
    """Base class for binary sensors."""

    def __init__(self, hass, name, icon):
        """Initialize the binary sensor."""
        self.hass = hass
        self._state = False
        self._attr_name = name
        self._attr_icon = icon

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._state

    def get_state(self, entity_id, default="off"):
        """Helper function to fetch sensor states safely."""
        state = self.hass.states.get(entity_id)
        return state.state if state else default

class ChargingFailureSensor(BaseEVBinarySensor):
    """Detects when charging fails (charger is active but no power is drawn)."""

    def __init__(self, hass):
        super().__init__(hass, "Charging Failure Detected", "mdi:alert-circle")

    def update(self):
        charger_status = self.get_state("sensor.charger_status", "unplugged")
        charger_power = float(self.get_state("sensor.charger_power", 0))

        self._state = charger_status == "charging" and charger_power == 0

class PublicChargingDetectionSensor(BaseEVBinarySensor):
    """Detects when the vehicle is plugged into a public charger (not home)."""

    def __init__(self, hass):
        super().__init__(hass, "Public Charging Detected", "mdi:ev-station")

    def update(self):
        car_plugged_in = self.get_state("binary_sensor.vehicle_charging_cable_connected", "off")
        home_charger_active = self.get_state("binary_sensor.charger_active", "off")

        self._state = car_plugged_in == "on" and home_charger_active == "off"