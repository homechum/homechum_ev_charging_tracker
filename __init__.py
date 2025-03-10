"""HomeChum EV Charging Tracker Custom Component."""
import logging

DOMAIN = "homechum_ev_charging_tracker"

_LOGGER = logging.getLogger(__name__)

def setup(hass, config):
    """Set up the HomeChum EV Charging Tracker component."""
    _LOGGER.info("HomeChum EV Charging Tracker has been loaded successfully")
    return True