"""Binary sensor platform for HomeChum EV Charging Tracker."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config_entry, async_add_entities, discovery_info=None):
    """Set up binary sensor entities from a config entry."""
    async_add_entities([PublicChargingDetectedSensor(hass)])

class PublicChargingDetectedSensor(BinarySensorEntity):
    """Binary sensor: Public Charging Detected."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "Public Charging Detected"
        self._attr_unique_id = "ev_public_charge_detected"
        self._attr_state = False  # Default state is False

    @property
    def is_on(self):
        """Determine if public charging is detected."""
        charging_state = self.hass.states.get("switch.myida_charging")
        location_state = self.hass.states.get("device_tracker.myida_position")
        ohme_status = self.hass.states.get("sensor.ohme_epod_status")

        if not charging_state or not location_state or not ohme_status:
            return False  # If any state is unavailable, assume no public charging

        return (
            charging_state.state == "on" and
            location_state.state != "home" and
            ohme_status.state == "unplugged"
        )