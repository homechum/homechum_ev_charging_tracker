"""Binary sensor platform for HomeChum EV Charging Tracker."""
import logging
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

DOMAIN = "homechum_ev_charging_tracker"

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up binary sensor entities from configuration.yaml."""
    _LOGGER.debug("Setting up binary sensor: PublicChargingDetectedSensor")

    sensor = PublicChargingDetectedSensor(hass)
    async_add_entities([sensor])

    _LOGGER.debug(f"Sensor added: {sensor}")

    # Track state changes for relevant entities
    async_track_state_change_event(
        hass,
        [
            "switch.myida_charging",
            "device_tracker.myida_position",
            "sensor.ohme_epod_status"
        ],
        sensor.async_update_state
    )

    # Force an initial state update
    await sensor.async_update_state(None)
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
        """Return True if public charging is detected."""
        return self._attr_is_on

    async def async_update_state(self, event):
        """Update state when a tracked entity changes."""
        entity_id = event.data["entity_id"] if event else "initial_update"
        _LOGGER.debug(f"Updating binary sensor state due to change in {entity_id}")

        charging_state = self.hass.states.get("switch.myida_charging")
        location_state = self.hass.states.get("device_tracker.myida_position")
        ohme_status = self.hass.states.get("sensor.ohme_epod_status")

        _LOGGER.debug(
            f"Current states - Charging: {charging_state}, Location: {location_state}, Ohme: {ohme_status}"
        )

        if not charging_state or not location_state or not ohme_status:
            self._attr_is_on = False
        else:
            self._attr_is_on = (
                charging_state.state == "on"
                and location_state.state != "home"
                and ohme_status.state == "unplugged"
            )

        _LOGGER.debug(f"Sensor new state: {self._attr_is_on}")
        self.async_write_ha_state()