"""Binary sensor platform for HomeChum EV Charging Tracker."""
import logging
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change

DOMAIN = "homechum_ev_charging_tracker"  # Ensure `const.py` exists with `DOMAIN` defined.

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up binary sensor entities from a config entry."""
    sensor = PublicChargingDetectedSensor(hass)
    async_add_entities([sensor])

    # Track state changes for relevant entities
    async_track_state_change(hass, "switch.myida_charging", sensor.async_update_state)
    async_track_state_change(hass, "device_tracker.myida_position", sensor.async_update_state)
    async_track_state_change(hass, "sensor.ohme_epod_status", sensor.async_update_state)

class PublicChargingDetectedSensor(BinarySensorEntity):
    """Binary sensor: Public Charging Detected."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "Public Charging Detected"
        self._attr_unique_id = "ev_public_charge_detected"
        self._attr_is_on = False  # Default state is False

    @property
    def is_on(self):
        """Determine if public charging is detected."""
        return self._attr_is_on

    @callback
    def async_update_state(self, entity_id, old_state, new_state):
        """Update state when a tracked entity changes."""
        charging_state = self.hass.states.get("switch.myida_charging")
        location_state = self.hass.states.get("device_tracker.myida_position")
        ohme_status = self.hass.states.get("sensor.ohme_epod_status")

        if not charging_state or not location_state or not ohme_status:
            self._attr_is_on = False
        else:
            self._attr_is_on = (
                charging_state.state == "on"
                and location_state.state != "home"
                and ohme_status.state == "unplugged"
            )

        self.async_write_ha_state()  # Force HA to update the sensor state
