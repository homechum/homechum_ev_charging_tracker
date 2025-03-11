"""Binary sensor platform for HomeChum EV Charging Tracker."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up binary sensor entities from a config entry."""
    async_add_entities([PublicChargingDetectedSensor(hass)])

class PublicChargingDetectedSensor(BinarySensorEntity):
    """Binary sensor: Public Charging Detected."""

    _attr_name = "Public Charging Detected"

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    @property
    def is_on(self):
        cable_state = self.hass.states.get("binary_sensor.myida_charging_cable_connected")
        ohme_status = self.hass.states.get("sensor.ohme_epod_status")
        if cable_state is None or ohme_status is None:
            return False
        # A connected cable and an "unplugged" Ohme status indicate a public charger is detected.
        return cable_state.state == "on" and ohme_status.state == "unplugged"