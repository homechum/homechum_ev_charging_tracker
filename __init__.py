"""HomeChum EV Charging Tracker Custom Component."""
import logging
import asyncio
from homeassistant.core import HomeAssistant

DOMAIN = "homechum_ev_charging_tracker"
_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the EV Charging Tracker component."""
    _LOGGER.info("EV Charging Tracker successfully loaded")
    return True