import asyncio
import logging
from typing import Any, Optional

#
# 1) Define Mocks for Home Assistant environment
#

class MockState:
    """Simple container for an entity's state."""
    def __init__(self, state: Any):
        self.state = state

class MockHass:
    """Mock HomeAssistant-like object storing states in a dictionary."""
    def __init__(self):
        # Dictionary: entity_id -> MockState
        self._states = {}
    
    def states(self, entity_id: str) -> Optional[MockState]:
        """Mimic hass.states.get(entity_id)."""
        return self.get(entity_id)
    
    def get(self, entity_id: str) -> Optional[MockState]:
        return self._states.get(entity_id)
    
    def set_state(self, entity_id: str, new_state: Any):
        """Set a new state for testing; triggers manual callback if needed."""
        self._states[entity_id] = MockState(new_state)

#
# 2) Minimal stubs for async_track_state_change_event functionality
#
#    In real HA, this sets up an event listener. Here, we'll just store
#    the callback and manually call it ourselves to simulate state changes.

def async_track_state_change_event(hass, entity_ids, callback):
    """Fake subscription. We'll manually call callback when we want."""
    # We'll store a reference to the sensor callback, so we can invoke it.
    # In real HA, the system triggers it automatically on state changes.
    pass  # Not strictly needed in this test harness

#
# 3) Utility function and the ChargeToChargeEfficiencySensor
#

def get_float_state(hass: MockHass, entity_id: str, default: float = None) -> float | None:
    """Helper to safely get a float value from an entity state."""
    state_obj = hass.get(entity_id)
    if not state_obj or state_obj.state in ("unknown", "unavailable", None):
        return default
    try:
        return float(state_obj.state)
    except (ValueError, TypeError):
        return default

class RestoreEntity:
    """Minimal stub for restore logic. We'll just store a last known state."""
    async def async_get_last_state(self):
        return None  # We won't do real restore in this example

class SensorEntity:
    """Minimal stub for a Home Assistant sensor entity."""
    pass

class ChargeToChargeEfficiencySensor(SensorEntity, RestoreEntity):
    def __init__(self, hass: MockHass):
        self.hass = hass
        self._attr_name = "EV Charge to Charge Efficiency"
        self._attr_unique_id = "ev_charge_to_charge_efficiency"
        self._attr_unit_of_measurement = "mi/%"
        self._attr_state = None

        self.last_miles: float | None = None
        self.last_soc: float | None   = None
        self.was_charging = False
        
        _LOGGER.info("Initializing ChargeToChargeEfficiencySensor")

        async_track_state_change_event(
            hass,
            ["binary_sensor.myida_charging_cable_connected", "switch.myida_charging"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore the last known efficiency value after a restart (stubbed)."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._attr_state = float(last_state.state)
                _LOGGER.info("Restored efficiency state: %s", self._attr_state)
            except ValueError:
                _LOGGER.warning("Stored state was invalid float: %s", last_state.state)

    async def async_update_callback(self, event):
        """Simulate what would be triggered in HA on a state-change event."""
        _LOGGER.debug(f"State change event fired: {event}")
        self.async_schedule_update_ha_state(force_refresh=True)

    def async_schedule_update_ha_state(self, force_refresh: bool = False):
        """Immediately call our property-based update logic."""
        # In real HA, this queues an update. Here we just do it inline.
        current_state = self.state
        _LOGGER.info(f"Sensor state is now: {current_state}")

    @property
    def state(self):
        """Calculate and return the charge-to-charge efficiency."""
        cable_state = self.hass.get("binary_sensor.myida_charging_cable_connected")
        charging_state = self.hass.get("switch.myida_charging")

        if cable_state is None or charging_state is None:
            return self._attr_state

        cable_connected = (cable_state.state == "on")
        charging = (charging_state.state == "on")

        if cable_connected and charging:
            # Charging started
            self.was_charging = True
            return self._attr_state

        if not cable_connected and self.was_charging:
            # Cable unplugged after successful charge → calculate efficiency
            miles_now = get_float_state(self.hass, "sensor.myida_odometer")
            soc_now = get_float_state(self.hass, "sensor.myida_battery_level")

            if (
                miles_now is not None and
                soc_now   is not None and
                self.last_miles is not None and
                self.last_soc   is not None
            ):
                if soc_now < self.last_soc:
                    soc_used = self.last_soc - soc_now
                    miles_travelled = miles_now - self.last_miles
                    if soc_used > 0:
                        self._attr_state = round(miles_travelled / soc_used, 2)
                        _LOGGER.info("Updated efficiency to: %s", self._attr_state)

            self.was_charging = False
            return self._attr_state

        if not cable_connected:
            # Cable unplugged, not charging → store baseline for next charge cycle
            self.last_miles = get_float_state(self.hass, "sensor.myida_odometer")
            self.last_soc   = get_float_state(self.hass, "sensor.myida_battery_level")

        return self._attr_state


#
# 4) Let's walk through a test scenario end-to-end
#

_LOGGER = logging.getLogger(__name__)

async def main():
    # Set up logging
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    # Create our fake hass environment
    hass = MockHass()

    # Create and add our sensor
    sensor = ChargeToChargeEfficiencySensor(hass)
    await sensor.async_added_to_hass()

    # Step A: Initially, car is unplugged, we set odometer=1000, battery=80
    hass.set_state("binary_sensor.myida_charging_cable_connected", "off")
    hass.set_state("switch.myida_charging", "off")
    hass.set_state("sensor.myida_odometer", 1000)
    hass.set_state("sensor.myida_battery_level", 80)

    # Because these states just changed, let's simulate an event callback
    # In real HA, each state change triggers an event. We'll do one "combined" event for demo:
    await sensor.async_update_callback({"entity_id": "initial_setup"})

    # Step B: Now user drives around (implicitly, cable is unplugged), so let's do nothing special here
    # But if we changed odometer or battery while unplugged, that's "driving."

    # Step C: Next time user plugs in cable to start charging
    _LOGGER.info("---- Plugging cable in and starting charge ----")
    hass.set_state("binary_sensor.myida_charging_cable_connected", "on")
    hass.set_state("switch.myida_charging", "on")
    await sensor.async_update_callback({"entity_id": "start_charging"})

    # Step D: Suppose charging finishes, but the user unplugs immediately afterwards.
    # Before that unplug, let's simulate user updated the odometer to 1200 and battery to 50
    # as though they had driven around before plugging in. Typically you'd do this while unplugged.
    hass.set_state("sensor.myida_odometer", 1200)
    hass.set_state("sensor.myida_battery_level", 50)

    _LOGGER.info("---- Unplugging cable after charging ----")
    hass.set_state("binary_sensor.myida_charging_cable_connected", "off")
    hass.set_state("switch.myida_charging", "off")
    await sensor.async_update_callback({"entity_id": "stop_charging"})

    _LOGGER.info(f"Final reported efficiency is: {sensor.state} mi/%")

if __name__ == "__main__":
    asyncio.run(main())