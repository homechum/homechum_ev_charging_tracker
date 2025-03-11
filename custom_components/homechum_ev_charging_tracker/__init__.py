"""HomeChum EV Charging Tracker integration."""
import logging
import datetime

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

DOMAIN = "homechum_ev_charging_tracker"
STORAGE_KEY = "homechum_ev_charging_tracker.public_sessions"
STORAGE_VERSION = 1

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HomeChum EV Charging Tracker integration."""
    
    # Initialize persistent storage for public charging sessions.
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load()
    if data is None:
        data = {"sessions": []}
    # Save the store and data in hass.data for later use.
    hass.data.setdefault(DOMAIN, {})["store"] = store
    hass.data[DOMAIN]["public_sessions"] = data

    async def handle_log_public_charging(call: ServiceCall) -> None:
        """Handle logging of a public charging session and store the data."""
        provider = call.data.get("provider")
        try:
            kwh = float(call.data.get("kwh", 0))
            cost = float(call.data.get("cost", 0))
            miles = float(call.data.get("miles", 0))
        except (ValueError, TypeError):
            _LOGGER.error("Invalid input data for public charging session: %s", call.data)
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

        # Optional: Trigger an immediate sensor update via dispatcher or update helper.
        # from homeassistant.helpers.dispatcher import async_dispatcher_send
        # async_dispatcher_send(hass, f"{DOMAIN}_update")

        # Create a persistent notification to confirm that the session was logged.
        hass.components.persistent_notification.create(
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
    
    return True