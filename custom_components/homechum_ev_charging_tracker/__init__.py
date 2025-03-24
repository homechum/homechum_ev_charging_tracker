"""HomeChum EV Charging Tracker integration."""
import logging
import datetime
import os

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.storage import Store
from homeassistant.components.persistent_notification import create as notify_create
from homeassistant.helpers.discovery import async_load_platform
from logging.handlers import TimedRotatingFileHandler

# Define log directory
log_dir = "/config/custom_components/homechum_ev_charging_tracker/logs"
os.makedirs(log_dir, exist_ok=True)  # Ensure the log directory exists

# Define log file path
log_file = os.path.join(log_dir, "homechum_ev_debug.log")

# Create logger
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

# Configure timed rotating file handler (rollover every 1 day, keep last 2 day of logs)
file_handler = TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=2, encoding="utf-8")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Add handler to logger
_LOGGER.addHandler(file_handler)

def setup(hass, config):
    _LOGGER.info("HOMECHUM: Initializing HomeChum EV Charging Tracker Component")
    return True

DOMAIN = "homechum_ev_charging_tracker"
STORAGE_KEY = "homechum_ev_charging_tracker.public_sessions"
STORAGE_VERSION = 1

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HomeChum EV Charging Tracker integration."""
    
    _LOGGER.debug("HOMECHUM: Initializing HomeChum EV Charging Tracker integration...")
    # 🔹 Ensure Home Assistant loads the sensor and binary_sensor platforms
    _LOGGER.debug("HOMECHUM: Loading sensor and binary sensor platforms...")
    hass.async_create_task(async_load_platform(hass, "sensor", DOMAIN, {}, config))
    hass.async_create_task(async_load_platform(hass, "binary_sensor", DOMAIN, {}, config))

    _LOGGER.debug("HomeChum EV Charging Tracker setup complete.")

    return True