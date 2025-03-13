"""Binary sensor platform for HomeChum EV Charging Tracker."""
import logging
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.components.binary_sensor import BinarySensorEntity

DOMAIN = "homechum_ev_charging_tracker"

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up binary sensor entities from configuration.yaml."""
    _LOGGER.debug("Setting up binary sensor: PublicChargingDetectedSensor")

    sensor = PublicChargingDetectedSensor(hass)
    async_add_entities([sensor])

    _LOGGER.debug(f"Sensor added: {sensor}")

    # Track state changes for relevant entities
    async_track_state_change_event(hass, "switch.myida_charging", sensor.async_update_state)
    async_track_state_change_event(hass, "device_tracker.myida_position", sensor.async_update_state)
    async_track_state_change_event(hass, "sensor.ohme_epod_status", sensor.async_update_state)

    # Force an initial state update
    sensor.async_update_state(None, None, None)
    _LOGGER.debug("Initial state update triggered")

class PublicChargingDetectedSensor(BinarySensorEntity):
    """Binary sensor: Public Charging Detected."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Public Charging Detected"
        self._attr_unique_id = "ev_public_charge_detected"
        self._attr_is_on = False  # Default state is False

    @property
    def is_on(self):
        """Return if the sensor is currently ON (public charging detected)."""
        return self._attr_is_on

    @callback
    def async_update_state(self, entity_id, old_state, new_state):
        """Update state when a tracked entity changes."""
        _LOGGER.debug(f"Updating binary sensor state due to change in {entity_id}")

        charging_state = self.hass.states.get("switch.myida_charging")
        location_state = self.hass.states.get("device_tracker.myida_position")
        ohme_status = self.hass.states.get("sensor.ohme_epod_status")

        if charging_state:
            _LOGGER.debug(f"Charging state: {charging_state.state}")
        if location_state:
            _LOGGER.debug(f"Location state: {location_state.state}")
        if ohme_status:
            _LOGGER.debug(f"Ohme status: {ohme_status.state}")

        if not charging_state or not location_state or not ohme_status:
            self._attr_is_on = False
        else:
            self._attr_is_on = (
                charging_state.state == "on"
                and location_state.state != "home"
                and ohme_status.state == "unplugged"
            )

        _LOGGER.debug(f"Sensor new state: {self._attr_is_on}")
        self.async_write_ha_state()  # Force HA to update the sensor state
