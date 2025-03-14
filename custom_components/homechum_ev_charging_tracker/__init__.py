"""HomeChum EV Charging Tracker integration."""
import logging
import datetime
import os

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.storage import Store
from homeassistant.components.persistent_notification import create as notify_create
from homeassistant.helpers.discovery import async_load_platform

log_dir = "/config/custom_components/homechum_ev_charging_tracker/logs"
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, "homechum_ev_debug.log")
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(log_file, mode='a')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
_LOGGER.addHandler(file_handler)

def setup(hass, config):
    _LOGGER.info("Initializing HomeChum EV Charging Tracker")
    return True

DOMAIN = "homechum_ev_charging_tracker"
STORAGE_KEY = "homechum_ev_charging_tracker.public_sessions"
STORAGE_VERSION = 1

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HomeChum EV Charging Tracker integration."""
    
    _LOGGER.debug("Initializing HomeChum EV Charging Tracker integration...")

    # Initialize persistent storage for public charging sessions.
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load()
    if data is None:
        data = {"sessions": []}

    # Save the store and data in hass.data for later use.
    hass.data.setdefault(DOMAIN, {})["store"] = store
    hass.data[DOMAIN]["public_sessions"] = data

    # 🔹 Ensure Home Assistant loads the sensor and binary_sensor platforms
    _LOGGER.debug("Loading sensor and binary sensor platforms...")
    hass.async_create_task(async_load_platform(hass, "sensor", DOMAIN, {}, config))
    hass.async_create_task(async_load_platform(hass, "binary_sensor", DOMAIN, {}, config))

    async def handle_log_public_charging(call: ServiceCall) -> None:
        """Handle logging of a public charging session and store the data."""
        provider = call.data.get("provider")
        try:
            kwh = float(call.data.get("kwh", 0))
            cost = float(call.data.get("cost", 0))
            miles = float(call.data.get("miles", 0))
        except (ValueError, TypeError) as e:
            _LOGGER.exception("Invalid input data for public charging session: %s", call.data, e)
            return

        session = {
            "provider": provider,
            "kwh": kwh,
            "cost": cost,
            "miles": miles,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        _LOGGER.info("Logging public charging session: %s", session)
        
        # Retrieve the stored data and update with the new session.
        store_data = hass.data[DOMAIN].get("public_sessions", {"sessions": []})
        store_data["sessions"].append(session)
        
        # Save the updated data back to persistent storage.
        await store.async_save(store_data)
        hass.data[DOMAIN]["public_sessions"] = store_data

        # Create a persistent notification to confirm that the session was logged.
        notify_create(
            hass,
            (
                f"Public Charging Session Logged:\n"
                f"Provider: {provider}\n"
                f"Energy: {kwh} kWh\n"
                f"Cost: £{cost}\n"
                f"Miles: {miles}"
            ),
            title="Public Charging Logged"
        )
    
    # Register the custom service that logs and stores public charging sessions.
    hass.services.async_register(
        DOMAIN, "log_public_charging", handle_log_public_charging
    )

    _LOGGER.debug("HomeChum EV Charging Tracker setup complete.")

    return True