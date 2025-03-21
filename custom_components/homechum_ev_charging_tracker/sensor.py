"""Sensor platform for HomeChum EV Charging Tracker."""
import logging
import asyncio
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.event import (async_track_state_change_event, async_call_later)
from homeassistant.helpers.entity import Entity

DOMAIN = "homechum_ev_charging_tracker"
# Delay to calculate drive to drive efficiency in sec
DEBOUNCE_DELAY_SECONDS = 900
_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    """Set up the component via configuration.yaml."""
    hass.helpers.discovery.load_platform("sensor", DOMAIN, {}, config)
    return True

def get_float_state(hass: HomeAssistant, entity_id: str) -> float | None:
    """Utility to safely get a float state from an entity."""
    state_obj = hass.states.get(entity_id)
    if state_obj and state_obj.state not in ("unknown", "unavailable", None):
        try:
            return float(state_obj.state)
        except ValueError:
            return None
    return None

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up sensor entities from a config entry."""
    _LOGGER.debug("Initializing HomeChum EV Charging Tracker sensors...")

    sensors = [
        ChargeToChargeEfficiencySensor(hass),
        DriveToDriveEfficiencySensor(hass),
        ContinuousEfficiencySensor(hass),
        IdleSoCLossSensor(hass),
        HomeEnergyConsumptionPerChargeSensor(hass),
        PublicEnergyConsumptionPerSessionSensor(hass),
        TotalPublicEnergyConsumptionSensor(hass),
        PublicChargingCostPerSessionSensor(hass),
        TotalPublicChargingCostSensor(hass),
        HomeChargingCostPerSessionSensor(hass),
        TotalHomeChargingCostSensor(hass),
        HomeChargingSavingsPerSessionSensor(hass),
        TotalHomeChargingSavingsSensor(hass),
        ChargeToChargeMilesPerKWhSensor(hass),
        DriveToDriveMilesPerKWhSensor(hass),
        #ContinuousMilesPerKWhSensor(hass)
    ]
    _LOGGER.debug(f"Adding sensors: {sensors}")  # Log sensor instances
    async_add_entities(sensors, update_before_add=True)

class ChargeToChargeEfficiencySensor(SensorEntity, RestoreEntity):
    """Sensor to track efficiency from charge to charge, restoring state on restart."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the efficiency sensor."""
        self.hass = hass
        self._attr_name = "EV Charge to Charge Efficiency"
        self._attr_unique_id = "ev_charge_to_charge_efficiency"
        self._attr_native_unit_of_measurement = "mi/%"
        self._attr_state = 0 # Start tracking from zero

        self.last_miles: float | None = None
        self.last_soc: float | None = None
        self.was_charging = False  # Flag to track if actual charging occurred

        _LOGGER.info("Initializing ChargeToChargeEfficiencySensor")

        # Subscribe to state changes using async_track_state_change_event.
        async_track_state_change_event(
            hass,
            ["binary_sensor.myida_charging_cable_connected", "switch.myida_charging"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore the last known efficiency value after a restart."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._attr_state = float(last_state.state)
                _LOGGER.info("Restored efficiency state: %s", self._attr_state)
            except ValueError:
                _LOGGER.warning("Stored state was invalid float: %s", last_state.state)

    async def async_update_callback(self, event):
        """Triggered whenever the cable sensor or charging switch changes."""
        entity_id = event.data.get("entity_id")
        old_state_obj = event.data.get("old_state")
        new_state_obj = event.data.get("new_state")

        old_state = old_state_obj.state if old_state_obj else None
        new_state = new_state_obj.state if new_state_obj else None

        _LOGGER.debug(
            "State change event for %s: %s → %s. Forcing sensor refresh.",
            entity_id, old_state, new_state
        )
        # Force an immediate update of our sensor
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        """Calculate and return the charge-to-charge efficiency."""
        cable_state = self.hass.states.get("binary_sensor.myida_charging_cable_connected")
        charging_state = self.hass.states.get("switch.myida_charging")

        if cable_state is None or charging_state is None:
            # Entities unavailable; keep the last known efficiency.
            return self._attr_state

        cable_connected = (cable_state.state == "on")
        charging = (charging_state.state == "on")

        if cable_connected and charging:
            # Charging started: Mark this session as "charging detected"
            self.was_charging = True
            return self._attr_state  # Keep last known efficiency while charging

        if not cable_connected and self.was_charging:
            # Cable unplugged after a successful charge → Calculate efficiency
            miles_now = get_float_state(self.hass, "sensor.myida_odometer")
            soc_now = get_float_state(self.hass, "sensor.myida_battery_level")

            if (
                miles_now is not None
                and soc_now is not None
                and self.last_miles is not None
                and self.last_soc is not None
            ):
                if soc_now < self.last_soc:
                    soc_used = self.last_soc - soc_now
                    miles_travelled = miles_now - self.last_miles
                    if soc_used > 0:
                        self._attr_state = round(miles_travelled / soc_used, 2)
                        _LOGGER.info("Updated efficiency to: %s", self._attr_state)

            # Reset charging flag since charging session is complete
            self.was_charging = False
            return self._attr_state  # Keep updated efficiency value

        # If cable is unplugged (or becomes unplugged) but we never flagged a charging session,
        # we store the current miles & SoC as the baseline for the next charge.
        if not cable_connected:
            # Cable unplugged but was NOT charging → Store values for next charge cycle
            self.last_miles = get_float_state(self.hass, "sensor.myida_odometer")
            self.last_soc = get_float_state(self.hass, "sensor.myida_battery_level")

        return self._attr_state  # Keep last efficiency value until next valid charge cycle
    
class DriveToDriveEfficiencySensor(SensorEntity, RestoreEntity):
    """Sensor to track drive-to-drive efficiency, restoring state on restart."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Drive to Drive Efficiency"
        self._attr_unique_id = "ev_drive_to_drive_efficiency"
        self._attr_native_unit_of_measurement = "mi/%"
        self._attr_state = 0 # Start tracking from zero
        self.start_miles = None
        self.start_soc = None
        self.last_state_valid = False  # Track if the last state was valid
       
        # Keep reference to any scheduled "stop finalization" call
        self._stop_debounce_task = None

        _LOGGER.debug("DriveToDriveEfficiencySensor initialized.")

        # Track changes in the vehicle's movement state
        async_track_state_change_event(
            hass,
            ["binary_sensor.myida_vehicle_moving"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore last known state on restart."""
        _LOGGER.info("DriveToDriveEfficiencySensor added to Home Assistant.")
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._attr_state = float(last_state.state)
            except ValueError:
                self._attr_state = 0.0

    async def async_update_callback(self, event):
        """Triggered whenever the sensor value changes."""
        entity_id = event.data.get("entity_id")
        old_state_obj = event.data.get("old_state")
        new_state_obj = event.data.get("new_state")

        old_state = old_state_obj.state if old_state_obj else None
        new_state = new_state_obj.state if new_state_obj else None

        _LOGGER.debug(
            "State change event for %s: %s → %s. Forcing sensor refresh.",
            entity_id, old_state, new_state
        )
        # Force an immediate update of our sensor
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        """Determine the efficiency based on vehicle movement."""
        moving_state = self.hass.states.get("binary_sensor.myida_vehicle_moving")

        if moving_state is None:
            return self._attr_state  # Return last known efficiency if state is unavailable

        moving = moving_state.state == "on"

        if moving:
            if self.start_miles is None or self.start_soc is None:
                # Capture starting values when the car first moves
                self.start_miles = get_float_state(self.hass, "sensor.myida_odometer")
                self.start_soc = get_float_state(self.hass, "sensor.myida_battery_level")
                self.last_state_valid = False  # Reset validity
            return self._attr_state  # Maintain last efficiency while moving

        # The car has stopped, calculate efficiency immediately
        return self._calculate_efficiency()

    def _calculate_efficiency(self):
        """Calculate efficiency immediately when the car stops."""
        if self.start_miles is not None and self.start_soc is not None:
            miles_now = get_float_state(self.hass, "sensor.myida_odometer")
            soc_now = get_float_state(self.hass, "sensor.myida_battery_level")

            if miles_now is not None and soc_now is not None and soc_now < self.start_soc:
                soc_used = self.start_soc - soc_now
                miles_travelled = miles_now - self.start_miles

                if soc_used > 0:
                    self._attr_state = round(miles_travelled / soc_used, 2)

                self.last_state_valid = True  # Mark the efficiency as valid

        return self._attr_state  # Maintain efficiency value while stopped

class ContinuousEfficiencySensor(SensorEntity, RestoreEntity):
    """Sensor to track real-time efficiency (Miles per 1% SoC) continuously, only when SoC decreases."""
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Continuous Efficiency"
        self._attr_unique_id = "ev_continuous_efficiency"
        self._attr_native_unit_of_measurement = "mi/%"
        self._attr_state = None

        self.last_miles = None
        self.last_soc = None
        self.is_charging = False
        self.idle_energy_loss_detected = False

        # Subscribe to changes in battery level and charging state
        async_track_state_change_event(
            hass,
            ["sensor.myida_battery_level", "switch.myida_charging"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore the last known efficiency value after a restart."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._attr_state = float(last_state.state)
            except ValueError:
                _LOGGER.warning("Stored state was invalid float: %s", last_state.state)
                self._attr_state = None

    async def async_update_callback(self, event):
        """Triggered when the battery level or charging switch changes. """
        entity_id = event.data.get("entity_id")
        _LOGGER.debug("State change event from %s. Scheduling efficiency update.", entity_id)

        # Force the sensor state to recalc
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        """Calculate or return the last-known continuous efficiency (mi/%)."""
        miles_now = get_float_state(self.hass, "sensor.myida_odometer")
        soc_now = get_float_state(self.hass, "sensor.myida_battery_level")
        charging_state = self.hass.states.get("switch.myida_charging")

        if miles_now is None or soc_now is None or charging_state is None:
            return self._attr_state  # Keep last known value if data is missing

        charging = (charging_state.state == "on")

        if charging:
            # If we are charging, just preserve current efficiency and note that we're charging.
            self.is_charging = True
            return self._attr_state

        # If we haven't recorded a baseline yet, record the current values.
        if self.last_soc is None or self.last_miles is None:
            self.last_miles = miles_now
            self.last_soc = soc_now
            return self._attr_state

        # If SoC is decreasing, we do the main efficiency calculation
        if soc_now < self.last_soc:
            self.is_charging = False
            soc_used = self.last_soc - soc_now
            miles_travelled = miles_now - self.last_miles

            if miles_travelled == 0:
                # The car didn't move, but SoC dropped => idle energy loss
                self.idle_energy_loss_detected = True
            else:
                self.idle_energy_loss_detected = False
                if soc_used > 0:
                    self._attr_state = round(miles_travelled / soc_used, 2)

            # Update reference points for next iteration
            self.last_miles = miles_now
            self.last_soc = soc_now

        # If SoC is increasing => charging or was plugged in. Just record new baseline.
        elif soc_now > self.last_soc:
            self.last_miles = miles_now
            self.last_soc = soc_now
            self.is_charging = True

        # If soc_now == self.last_soc, no net change. Nothing to recalc.
        return self._attr_state

class IdleSoCLossSensor(SensorEntity, RestoreEntity):
    """Sensor to track energy lost when the car is idle (SoC drops while odometer remains unchanged)."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Idle Energy Loss"
        self._attr_unique_id = "ev_idle_energy_loss"
        self._attr_native_unit_of_measurement = "%"
        self._attr_state = 0  # Start tracking from zero
        self.last_soc = None
        self.last_miles = None

        async_track_state_change_event(
            hass,
            ["sensor.myida_battery_level", "sensor.myida_odometer"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore previous idle energy loss value after a restart."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            self._attr_state = float(last_state.state)

    async def async_update_callback(self, event):
        """Triggered when SoC or odometer changes."""
        entity_id = event.data.get("entity_id")
        _LOGGER.debug("State change event from %s. Scheduling efficiency update.", entity_id)
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        soc_now = get_float_state(self.hass, "sensor.myida_battery_level")
        miles_now = get_float_state(self.hass, "sensor.myida_odometer")

        if soc_now is None or miles_now is None:
            return self._attr_state  # Keep the last recorded idle loss if data is unavailable

        if self.last_soc is None or self.last_miles is None:
            self.last_soc = soc_now
            self.last_miles = miles_now
            return self._attr_state  

        if soc_now < self.last_soc and miles_now == self.last_miles:
            # SoC dropped, but odometer didn't increase → This is idle energy loss
            soc_lost = self.last_soc - soc_now
            self._attr_state += soc_lost  # Accumulate idle losses

        # Update last recorded values
        self.last_soc = soc_now
        self.last_miles = miles_now
        return self._attr_state
    
class HomeEnergyConsumptionPerChargeSensor(SensorEntity, RestoreEntity):
    """Sensor to track total energy consumed (kWh) per charge session (Home Charging Only)."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Home Energy Consumption Per Charge"
        self._attr_unique_id = "ev_home_energy_per_charge"
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_state = 0  # Start tracking from zero
        self.is_charging = False  # Flag to track if charging session is active

        async_track_state_change_event(
            hass,
            ["sensor.myida_charging_power", "switch.myida_charging", "binary_sensor.myida_charging_cable_connected", "binary_sensor.ev_public_charge_detected"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore previous charge session energy consumption after a restart."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            self._attr_state = float(last_state.state)

    #async def async_update_callback(self, entity_id, old_state, new_state):
    async def async_update_callback(self, entity_id):
        """Triggered when charging power, charging state, cable connection, or public charge detection changes."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        charging_power = get_float_state(self.hass, "sensor.myida_charging_power")
        charging_status = self.hass.states.get("switch.myida_charging")
        cable_connected = self.hass.states.get("binary_sensor.myida_charging_cable_connected")
        public_charging = self.hass.states.get("binary_sensor.ev_public_charge_detected")

        if charging_power is None or charging_status is None or cable_connected is None or public_charging is None:
            return self._attr_state  # Keep last recorded energy if data is unavailable

        charging = charging_status.state == "on"
        cable_plugged = cable_connected.state == "on"
        is_public_charging = public_charging.state == "on"

        if is_public_charging:
            # If public charging is detected, do not track home energy consumption
            return self._attr_state

        if charging and cable_plugged:
            self.is_charging = True
            if charging_power > 0:
                # Integrate energy consumption over time (assuming updates every 1 minute)
                self._attr_state += charging_power * (1 / 60)  # Convert kW to kWh per minute
        elif not cable_plugged and self.is_charging:
            # Charging cable unplugged → Charging session completed
            self.is_charging = False
            return self._attr_state  # Keep the recorded kWh until the next session

        if not charging and not cable_plugged:
            # Reset energy tracking when a new home charging session starts
            self._attr_state = 0

        return self._attr_state

class TotalHomeEnergyConsumptionSensor(SensorEntity, RestoreEntity):
    """Sensor to track total accumulated home charging energy consumption across multiple sessions."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "Total Home Charging Energy Consumption"
        self._attr_unique_id = "ev_total_home_energy"
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_state = 0  # Start tracking from zero
        self.last_session_energy = 0  # Stores the last session energy

        async_track_state_change_event(
            hass,
            ["sensor.ev_home_energy_per_charge", "binary_sensor.ev_public_charge_detected", "binary_sensor.myida_charging_cable_connected"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore total energy consumption after a restart."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            self._attr_state = float(last_state.state)

    #async def async_update_callback(self, entity_id, old_state, new_state):
    async def async_update_callback(self, entity_id):
        """Triggered when a charging session ends (cable unplugged or energy per charge session updates)."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        session_energy = get_float_state(self.hass, "sensor.ev_home_energy_per_charge")
        cable_connected = self.hass.states.get("binary_sensor.myida_charging_cable_connected")
        public_charging = self.hass.states.get("binary_sensor.ev_public_charge_detected")

        if session_energy is None or cable_connected is None or public_charging is None:
            return self._attr_state  # Keep the last recorded value if data is unavailable

        cable_plugged = cable_connected.state == "on"
        is_public_charging = public_charging.state == "on"

        if is_public_charging:
            return self._attr_state  # Ignore energy if public charging is detected

        if not cable_plugged and session_energy > 0 and session_energy != self.last_session_energy:
            # A charging session ended and the cable was unplugged → Add session energy to total
            self._attr_state += session_energy
            self.last_session_energy = session_energy  # Store last session value to prevent duplicate additions

        return self._attr_state

class PublicEnergyConsumptionPerSessionSensor(SensorEntity, RestoreEntity):
    """Sensor to track total energy consumed (kWh) per public charging session."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Public Energy Consumption Per Charge"
        self._attr_unique_id = "ev_public_energy_per_charge"
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_state = 0  # Start tracking from zero
        self.is_charging = False  # Track if a public charging session is active

        async_track_state_change_event(
            hass,
            ["sensor.myida_charging_power", "switch.myida_charging", "binary_sensor.myida_charging_cable_connected", "binary_sensor.ev_public_charge_detected"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore previous charge session energy consumption after a restart."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            self._attr_state = float(last_state.state)

    #async def async_update_callback(self, entity_id, old_state, new_state):
    async def async_update_callback(self, entity_id):
        """Triggered when charging power, charging state, cable connection, or public charge detection changes."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        charging_power = get_float_state(self.hass, "sensor.myida_charging_power")
        charging_status = self.hass.states.get("switch.myida_charging")
        cable_connected = self.hass.states.get("binary_sensor.myida_charging_cable_connected")
        public_charging = self.hass.states.get("binary_sensor.ev_public_charge_detected")

        if charging_power is None or charging_status is None or cable_connected is None or public_charging is None:
            return self._attr_state  # Keep last recorded energy if data is unavailable

        charging = charging_status.state == "on"
        cable_plugged = cable_connected.state == "on"
        is_public_charging = public_charging.state == "on"

        if not is_public_charging:
            return self._attr_state  # Ignore energy if public charging is not detected

        if charging and cable_plugged:
            self.is_charging = True
            if charging_power > 0:
                # Integrate energy consumption over time (assuming updates every 1 minute)
                self._attr_state += charging_power * (1 / 60)  # Convert kW to kWh per minute
        elif not cable_plugged and self.is_charging:
            # Public charging session completed
            self.is_charging = False
            return self._attr_state  # Keep the recorded kWh until the next session

        if not charging and not cable_plugged:
            # Reset energy tracking when a new public charging session starts
            self._attr_state = 0

        return self._attr_state

class TotalPublicEnergyConsumptionSensor(SensorEntity, RestoreEntity):
    """Sensor to track total accumulated public charging energy consumption across multiple sessions."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "Total Public Charging Energy Consumption"
        self._attr_unique_id = "ev_total_public_energy"
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_state = 0  # Start tracking from zero
        self.last_session_energy = 0  # Stores the last session energy

        async_track_state_change_event(
            hass,
            ["sensor.ev_public_energy_per_charge", "binary_sensor.ev_public_charge_detected", "binary_sensor.myida_charging_cable_connected"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore total public energy consumption after a restart."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            self._attr_state = float(last_state.state)

    #async def async_update_callback(self, entity_id, old_state, new_state):
    async def async_update_callback(self, entity_id):
        """Triggered when a public charging session ends (cable unplugged or energy per charge session updates)."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        session_energy = get_float_state(self.hass, "sensor.ev_public_energy_per_charge")
        cable_connected = self.hass.states.get("binary_sensor.myida_charging_cable_connected")
        public_charging = self.hass.states.get("binary_sensor.ev_public_charge_detected")

        if session_energy is None or cable_connected is None or public_charging is None:
            return self._attr_state  # Keep last recorded value if data is unavailable

        cable_plugged = cable_connected.state == "on"
        is_public_charging = public_charging.state == "on"

        if not is_public_charging:
            return self._attr_state  # Ignore updates when public charging is not active

        if not cable_plugged and session_energy > 0 and session_energy != self.last_session_energy:
            # A public charging session ended and the cable was unplugged → Add session energy to total
            self._attr_state += session_energy
            self.last_session_energy = session_energy  # Store last session value to prevent duplicate additions

        return self._attr_state

class PublicChargingCostPerSessionSensor(SensorEntity, RestoreEntity):
    """Sensor to calculate cost of public charging session with push notification for user input."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Public Charging Cost Per Session"
        self._attr_unique_id = "ev_public_charge_cost_per_session"
        self._attr_native_unit_of_measurement = "GBP"
        self._attr_state = 0  # Start tracking from zero
        self.last_session_energy = 0  # Stores the last session energy
        self.hass = hass  # Home Assistant instance to send notifications

        async_track_state_change_event(
            hass,
            ["sensor.ev_public_energy_per_charge", "input_number.ev_public_charge_cost_per_kwh", "binary_sensor.myida_charging_cable_connected", "binary_sensor.ev_public_charge_detected"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore cost value after a restart."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            self._attr_state = float(last_state.state)

    #async def async_update_callback(self, entity_id, old_state, new_state):
    async def async_update_callback(self, entity_id):
        """Triggered when energy per session, cost per kWh, or public charging status changes."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        session_energy = get_float_state(self.hass, "sensor.ev_public_energy_per_charge")
        cost_per_kwh = get_float_state(self.hass, "input_number.ev_public_charge_cost_per_kwh")
        cable_connected = self.hass.states.get("binary_sensor.myida_charging_cable_connected")
        public_charging = self.hass.states.get("binary_sensor.ev_public_charge_detected")

        if session_energy is None or cost_per_kwh is None or cable_connected is None or public_charging is None:
            return self._attr_state  # Keep last recorded value if data is unavailable

        cable_plugged = cable_connected.state == "on"
        is_public_charging = public_charging.state == "on"

        if not is_public_charging:
            return self._attr_state  # Ignore updates when public charging is not active

        if not cable_plugged and session_energy > 0 and session_energy != self.last_session_energy:
            # A public charging session ended, send push notification to user for cost input
            self.last_session_energy = session_energy  # Store session energy
            self.hass.loop.create_task(self.send_push_notification(session_energy))  # Schedule async call

        if self.last_session_energy > 0 and cost_per_kwh > 0:
            # Calculate total cost when user inputs the cost per kWh
            total_cost = self.last_session_energy * cost_per_kwh
            self._attr_state = round(total_cost, 2)  # Store the cost of the last session

        return self._attr_state

    async def send_push_notification(self, session_energy):
        """Send a push notification when a public charging session ends."""
        message = (
            f"Public Charging Session Ended 🚗⚡\n"
            f"Energy Used: {session_energy:.2f} kWh\n"
            "Please enter the cost per kWh in the Home Assistant app."
        )
        await self.hass.services.async_call(
            "notify",
            "mobile_app_bharaths_iphone",
            {
                "title": "Public Charging Cost Entry",
                "message": message,
                "data": {
                    "push": {
                        "category": "input_number.ev_public_charge_cost_per_kwh"
                    }
                },
            },
        )

class TotalPublicChargingCostSensor(SensorEntity, RestoreEntity):
    """Sensor to track total accumulated public charging cost across multiple sessions."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "Total Public Charging Cost"
        self._attr_unique_id = "ev_total_public_charge_cost"
        self._attr_native_unit_of_measurement = "GBP"
        self._attr_state = 0  # Start tracking from zero
        self.last_session_cost = 0  # Stores the last session cost

        async_track_state_change_event(
            hass,
            ["sensor.ev_public_charge_cost_per_session", "binary_sensor.ev_public_charge_detected", "binary_sensor.myida_charging_cable_connected"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore total public charging cost after a restart."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            self._attr_state = float(last_state.state)

    #async def async_update_callback(self, entity_id, old_state, new_state):
    async def async_update_callback(self, entity_id):
        """Triggered when a public charging session ends (cable unplugged or new cost is calculated)."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        session_cost = get_float_state(self.hass, "sensor.ev_public_charge_cost_per_session")
        cable_connected = self.hass.states.get("binary_sensor.myida_charging_cable_connected")
        public_charging = self.hass.states.get("binary_sensor.ev_public_charge_detected")

        if session_cost is None or cable_connected is None or public_charging is None:
            return self._attr_state  # Keep last recorded value if data is unavailable

        cable_plugged = cable_connected.state == "on"
        is_public_charging = public_charging.state == "on"

        if not is_public_charging:
            return self._attr_state  # Ignore updates when public charging is not active

        if not cable_plugged and session_cost > 0 and session_cost != self.last_session_cost:
            # A public charging session ended and the cable was unplugged → Add session cost to total
            self._attr_state += session_cost
            self.last_session_cost = session_cost  # Store last session value to prevent duplicate additions

        return self._attr_state

class HomeChargingCostPerSessionSensor(SensorEntity, RestoreEntity):
    """Sensor to calculate home charging cost per session with dynamic pricing and error handling."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Home Charging Cost Per Session"
        self._attr_unique_id = "ev_home_charge_cost_per_session"
        self._attr_native_unit_of_measurement = "GBP"
        self._attr_state = 0  # Start tracking from zero
        self.last_session_energy = 0  # Stores the last session energy

        async_track_state_change_event(
            hass,
            ["sensor.ev_home_energy_per_charge", "select.ohme_epod_charge_mode", "sensor.octopus_electricity_current_rate", "binary_sensor.ev_public_charge_detected", "binary_sensor.myida_charging_cable_connected"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore cost value after a restart."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            self._attr_state = float(last_state.state)

    #async def async_update_callback(self, entity_id, old_state, new_state):
    async def async_update_callback(self, entity_id):
        """Triggered when energy per session, cost per kWh, or home charging status changes."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        session_energy = get_float_state(self.hass, "sensor.ev_home_energy_per_charge")
        charge_mode_entity = self.hass.states.get("select.ohme_epod_charge_mode")  # ✅ Correctly fetch charge mode
        dynamic_rate = get_float_state(self.hass, "sensor.octopus_electricity_current_rate")
        cable_connected = self.hass.states.get("binary_sensor.myida_charging_cable_connected")
        public_charging = self.hass.states.get("binary_sensor.ev_public_charge_detected")

        # Handle missing or unavailable states
        if session_energy is None or dynamic_rate is None or cable_connected is None or public_charging is None:
            _LOGGER.warning("HomeChargingCostPerSessionSensor: Missing data from one or more required sensors.")
            return self._attr_state  # Keep last recorded value

        if charge_mode_entity is None or charge_mode_entity.state in (None, "unknown", "unavailable"):
            _LOGGER.warning("HomeChargingCostPerSessionSensor: Charge mode is unavailable. Using Octopus rate.")
            cost_per_kwh = dynamic_rate  # Default to variable pricing if charge mode is missing
        elif charge_mode_entity.state == "smart_charge":
            cost_per_kwh = 0.07  # Fixed rate for smart charging
        else:
            cost_per_kwh = dynamic_rate  # Default to Octopus variable pricing

        cable_plugged = cable_connected.state == "on"
        is_public_charging = public_charging.state == "on"

        if is_public_charging:
            return self._attr_state  # Ignore updates when public charging is detected

        if not cable_plugged and session_energy > 0 and session_energy != self.last_session_energy:
            # A home charging session ended, calculate cost
            total_cost = session_energy * cost_per_kwh
            self._attr_state = round(total_cost, 2)  # Store the cost of the last session
            self.last_session_energy = session_energy  # Store last session value to prevent duplicate calculations

            _LOGGER.info(
                f"Home Charging Session Ended: {session_energy:.2f} kWh used at {cost_per_kwh:.2f} GBP/kWh. Total Cost: {self._attr_state:.2f} GBP"
            )

        return self._attr_state

class TotalHomeChargingCostSensor(SensorEntity, RestoreEntity):
    """Sensor to track total accumulated home charging cost across multiple sessions."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "Total Home Charging Cost"
        self._attr_unique_id = "ev_total_home_charge_cost"
        self._attr_native_unit_of_measurement = "GBP"
        self._attr_state = 0  # Start tracking from zero
        self.last_session_cost = 0  # Stores the last session cost

        async_track_state_change_event(
            hass,
            ["sensor.ev_home_charge_cost_per_session", "binary_sensor.ev_public_charge_detected", "binary_sensor.myida_charging_cable_connected"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore total home charging cost after a restart."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            self._attr_state = float(last_state.state)

    #async def async_update_callback(self, entity_id, old_state, new_state):
    async def async_update_callback(self, entity_id):
        """Triggered when a home charging session ends (cable unplugged or new cost is calculated)."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        session_cost = get_float_state(self.hass, "sensor.ev_home_charge_cost_per_session")
        cable_connected = self.hass.states.get("binary_sensor.myida_charging_cable_connected")
        public_charging = self.hass.states.get("binary_sensor.ev_public_charge_detected")

        if session_cost is None or cable_connected is None or public_charging is None:
            return self._attr_state  # Keep last recorded value if data is unavailable

        cable_plugged = cable_connected.state == "on"
        is_public_charging = public_charging.state == "on"

        if is_public_charging:
            return self._attr_state  # Ignore updates when public charging is detected

        if not cable_plugged and session_cost > 0 and session_cost != self.last_session_cost:
            # A home charging session ended and the cable was unplugged → Add session cost to total
            self._attr_state += session_cost
            self.last_session_cost = session_cost  # Store last session value to prevent duplicate additions

            _LOGGER.info(
                f"Home Charging Session Cost Added: {session_cost:.2f} GBP | Total Home Charging Cost: {self._attr_state:.2f} GBP"
            )

        return self._attr_state

class HomeChargingSavingsPerSessionSensor(SensorEntity, RestoreEntity):
    """Sensor to calculate home charging savings per session compared to Octopus tariff."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Home Charging Savings Per Session"
        self._attr_unique_id = "ev_home_charge_savings_per_session"
        self._attr_native_unit_of_measurement = "GBP"
        self._attr_state = 0  # Start tracking from zero

        async_track_state_change_event(
            hass,
            ["sensor.ev_home_charge_cost_per_session", "sensor.ev_home_energy_per_charge", "select.ohme_epod_charge_mode", "sensor.octopus_electricity_current_rate", "binary_sensor.ev_public_charge_detected", "binary_sensor.myida_charging_cable_connected"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore savings value after a restart."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            self._attr_state = float(last_state.state)

    #async def async_update_callback(self, entity_id, old_state, new_state):
    async def async_update_callback(self, entity_id):
        """Triggered when a home charging session ends."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        session_cost = get_float_state(self.hass, "sensor.ev_home_charge_cost_per_session")
        session_energy = get_float_state(self.hass, "sensor.ev_home_energy_per_charge")
        charge_mode = self.hass.states.get("select.ohme_epod_charge_mode")
        octopus_rate = get_float_state(self.hass, "sensor.octopus_electricity_current_rate")
        cable_connected = self.hass.states.get("binary_sensor.myida_charging_cable_connected")
        public_charging = self.hass.states.get("binary_sensor.ev_public_charge_detected")

        if session_cost is None or session_energy is None or charge_mode is None or octopus_rate is None or cable_connected is None or public_charging is None:
            return self._attr_state  # Keep last recorded value if data is unavailable

        cable_plugged = cable_connected.state == "on"
        is_public_charging = public_charging.state == "on"

        if is_public_charging:
            return self._attr_state  # Ignore updates when public charging is detected

        # Determine the rate user paid for charging
        if charge_mode.state == "smart_charge":
            actual_cost_per_kwh = 0.07  # Fixed rate for smart charging
        else:
            actual_cost_per_kwh = octopus_rate  # Octopus variable pricing

        # Calculate what the cost *would* have been at the full Octopus tariff
        normal_cost = session_energy * octopus_rate
        actual_cost = session_energy * actual_cost_per_kwh

        savings = normal_cost - actual_cost  # Difference = savings
        self._attr_state = round(savings, 2)

        _LOGGER.info(
            f"Home Charging Savings Calculated: {session_energy:.2f} kWh, Saved: {savings:.2f} GBP"
        )

        return self._attr_state

class TotalHomeChargingSavingsSensor(SensorEntity, RestoreEntity):
    """Sensor to track total accumulated home charging savings compared to Octopus tariff."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "Total Home Charging Savings"
        self._attr_unique_id = "ev_total_home_charge_savings"
        self._attr_native_unit_of_measurement = "GBP"
        self._attr_state = 0  # Start tracking from zero
        self.last_session_savings = 0  # Stores the last session savings

        async_track_state_change_event(
            hass,
            ["sensor.ev_home_charge_savings_per_session", "binary_sensor.ev_public_charge_detected", "binary_sensor.myida_charging_cable_connected"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore total savings after a restart."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            self._attr_state = float(last_state.state)

    #async def async_update_callback(self, entity_id, old_state, new_state):
    async def async_update_callback(self, entity_id):
        """Triggered when a home charging session ends."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        session_savings = get_float_state(self.hass, "sensor.ev_home_charge_savings_per_session")
        cable_connected = self.hass.states.get("binary_sensor.myida_charging_cable_connected")
        public_charging = self.hass.states.get("binary_sensor.ev_public_charge_detected")

        if session_savings is None or cable_connected is None or public_charging is None:
            return self._attr_state  # Keep last recorded value if data is unavailable

        cable_plugged = cable_connected.state == "on"
        is_public_charging = public_charging.state == "on"

        if is_public_charging:
            return self._attr_state  # Ignore updates when public charging is detected

        if not cable_plugged and session_savings > 0 and session_savings != self.last_session_savings:
            # A home charging session ended → Add session savings to total
            self._attr_state += session_savings
            self.last_session_savings = session_savings  # Store last session value to prevent duplicate additions

            _LOGGER.info(
                f"Home Charging Savings Added: {session_savings:.2f} GBP | Total Savings: {self._attr_state:.2f} GBP"
            )

        return self._attr_state

class ChargeToChargeMilesPerKWhSensor(SensorEntity, RestoreEntity):
    """Sensor to calculate Charge-to-Charge efficiency in miles/kWh based on previous charge cycle."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "Charge-to-Charge Efficiency (Miles/kWh)"
        self._attr_unique_id = "ev_charge_to_charge_miles_per_kwh"
        self._attr_native_unit_of_measurement = "mi/kWh"
        self._attr_state = None  # Efficiency starts as unknown
        self.last_miles = None
        self.last_energy = None
        self.charging_detected = False  # Track if an actual charging session happened

        async_track_state_change_event(
            hass,
            ["sensor.myida_odometer", "sensor.ev_home_energy_per_charge", "sensor.ev_public_energy_per_charge", "binary_sensor.myida_charging_cable_connected", "switch.myida_charging"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore efficiency after a restart."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            self._attr_state = float(last_state.state)

    #async def async_update_callback(self, entity_id, old_state, new_state):
    async def async_update_callback(self, entity_id):
        """Triggered when odometer, energy consumption, or charging state changes."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        miles_now = get_float_state(self.hass, "sensor.myida_odometer")
        home_energy = get_float_state(self.hass, "sensor.ev_home_energy_per_charge")
        public_energy = get_float_state(self.hass, "sensor.ev_public_energy_per_charge")
        cable_connected = self.hass.states.get("binary_sensor.myida_charging_cable_connected")
        charging_status = self.hass.states.get("switch.myida_charging")

        if miles_now is None or home_energy is None or public_energy is None or cable_connected is None or charging_status is None:
            return self._attr_state  # Keep last recorded efficiency if data is unavailable

        total_energy_used = home_energy + public_energy  # Total kWh used since last charge
        cable_plugged = cable_connected.state == "on"
        is_charging = charging_status.state == "on"

        if is_charging and cable_plugged:
            # A new charging session has started
            if self.charging_detected:
                # Calculate efficiency only if we have a valid last recorded session
                if self.last_miles is not None and self.last_energy is not None:
                    miles_travelled = miles_now - self.last_miles
                    if self.last_energy > 0:
                        efficiency = miles_travelled / self.last_energy
                        self._attr_state = round(efficiency, 2)

                        _LOGGER.info(
                            f"Charge-to-Charge Efficiency Calculated: {miles_travelled:.2f} miles / {self.last_energy:.2f} kWh = {self._attr_state:.2f} mi/kWh"
                        )

            # Store new reference values for the next charge cycle
            self.last_miles = miles_now
            self.last_energy = total_energy_used
            self.charging_detected = True  # Mark this as a valid charging session

        elif not cable_plugged and not is_charging:
            # Charging session has fully ended
            self.charging_detected = False  # Reset for the next valid charging cycle

        return self._attr_state

class DriveToDriveMilesPerKWhSensor(SensorEntity, RestoreEntity):
    """Sensor to calculate Drive-to-Drive efficiency in miles/kWh based on energy used while driving."""

    BATTERY_CAPACITY_KWH = 77  # Fixed battery capacity assumption

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "Drive-to-Drive Efficiency (Miles/kWh)"
        self._attr_unique_id = "ev_drive_to_drive_miles_per_kwh"
        self._attr_native_unit_of_measurement = "mi/kWh"
        self._attr_state = "unknown"  # Proper initialization for numeric sensor
        self.last_miles = None
        self.last_energy = None
        self.last_soc = None  # Track battery level for energy estimation
        self.driving_detected = False  # Track if an actual drive session happened

        async_track_state_change_event(
            hass,
            ["sensor.myida_odometer", "sensor.myida_battery_level", "binary_sensor.myida_vehicle_moving"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore efficiency after a restart."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            self._attr_state = float(last_state.state)  # Ensure restored state is a valid float

    #async def async_update_callback(self, entity_id, old_state, new_state):
    async def async_update_callback(self, entity_id):
        """Triggered when odometer, energy consumption, battery level, or driving state changes."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        miles_now = get_float_state(self.hass, "sensor.myida_odometer")
        #energy_used = get_float_state(self.hass, "sensor.myida_energy_used")  # Direct energy measurement
        battery_level = get_float_state(self.hass, "sensor.myida_battery_level")
        vehicle_moving = self.hass.states.get("binary_sensor.myida_vehicle_moving")

        if miles_now is None or battery_level is None or vehicle_moving is None:
            return self._attr_state  # Keep last recorded efficiency if data is unavailable

        is_moving = vehicle_moving.state == "on"

        if is_moving:
            # A new driving session has started
            self.driving_detected = True  # Track this drive session
            return self._attr_state  # No update yet

        if not is_moving and self.driving_detected:
            # Car has stopped moving → Calculate efficiency from previous drive cycle
            if self.last_miles is not None and self.last_energy is not None:
                miles_travelled = miles_now - self.last_miles

                #if energy_used is not None:
                #    total_energy_used = energy_used  # Prefer direct measurement
                #else:
                # Estimate energy used from battery SoC drop
                if self.last_soc is not None:
                    soc_drop = self.last_soc - battery_level
                    if soc_drop > 0:
                        total_energy_used = (soc_drop / 100) * self.BATTERY_CAPACITY_KWH
                    else:
                        total_energy_used = None  # No valid energy change
                else:
                    total_energy_used = None

                if total_energy_used is not None and total_energy_used > 0:
                    efficiency = miles_travelled / total_energy_used
                    self._attr_state = round(efficiency, 2)

                    _LOGGER.info(
                        f"Drive-to-Drive Efficiency Calculated: {miles_travelled:.2f} miles / {total_energy_used:.2f} kWh = {self._attr_state:.2f} mi/kWh"
                    )
                else:
                    _LOGGER.warning("DriveToDriveMilesPerKWhSensor: No valid energy consumption detected.")

            # Store new reference values for the next drive cycle
            self.last_miles = miles_now
            self.last_energy = total_energy_used
            self.last_soc = battery_level
            self.driving_detected = False  # Reset for the next valid drive cycle

        return self._attr_state

# class ContinuousMilesPerKWhSensor(SensorEntity, RestoreEntity):
#     """Continuously calculates efficiency in miles/kWh, ignoring charging and SoC increases."""

#     BATTERY_CAPACITY_KWH = 77  # Fixed battery capacity assumption

#     def __init__(self, hass: HomeAssistant):
#         self.hass = hass
#         self._attr_name = "Continuous Efficiency (Miles/kWh)"
#         self._attr_unique_id = "ev_continuous_miles_per_kwh"
#         self._attr_native_unit_of_measurement = "mi/kWh"
#         self._attr_state = "unknown"  # Proper initialization for numeric sensor
#         self.last_miles = None
#         self.last_energy = None
#         self.last_soc = None

#         async_track_state_change_event(
#             hass,
#             ["sensor.myida_odometer", "sensor.myida_battery_level", "binary_sensor.myida_vehicle_moving", "switch.myida_charging"],
#             self.async_update_callback
#         )

#     async def async_added_to_hass(self):
#         """Restore efficiency value after a restart."""
#         last_state = await self.async_get_last_state()
#         if last_state and last_state.state not in (None, "unknown", "unavailable"):
#             try:
#                 self._attr_state = float(last_state.state)  # Ensure restored state is a valid float
#             except ValueError:
#                 _LOGGER.warning("ContinuousMilesPerKWhSensor: Failed to restore state, setting to unknown.")
#                 self._attr_state = "unknown"

#       #async def async_update_callback(self, entity_id, old_state, new_state):
#      async def async_update_callback(self, entity_id):
#         """Triggered when odometer, energy consumption, battery level, or driving state changes."""
#         self.async_schedule_update_ha_state(force_refresh=True)

#     @property
#     def state(self):
#         miles_now = get_float_state(self.hass, "sensor.myida_odometer")
#         energy_used = get_float_state(self.hass, "sensor.myida_energy_used")
#         battery_level = get_float_state(self.hass, "sensor.myida_battery_level")
#         is_moving = self.hass.states.get("binary_sensor.myida_vehicle_moving").state == "on"
#         is_charging = self.hass.states.get("switch.myida_charging").state == "on"

#         if miles_now is None or battery_level is None:
#             _LOGGER.warning("ContinuousMilesPerKWhSensor: Missing odometer or battery level data.")
#             return self._attr_state  # Keep last recorded efficiency if data is unavailable

#         if is_charging or (self.last_soc is not None and battery_level > self.last_soc):
#             return self._attr_state  # Ignore calculations during charging or SoC increase

#         if self.last_miles is not None and self.last_energy is not None:
#             miles_travelled = miles_now - self.last_miles

#             #if energy_used is not None:
#             #    total_energy_used = energy_used  # Prefer direct measurement
#             #else:
#             # Estimate energy used from battery SoC drop
#             if self.last_soc is not None:
#                 soc_drop = self.last_soc - battery_level
#                 if soc_drop > 0:
#                     total_energy_used = (soc_drop / 100) * self.BATTERY_CAPACITY_KWH
#                 else:
#                     total_energy_used = None  # No valid energy change
#             else:
#                 total_energy_used = None

#             if total_energy_used is not None and total_energy_used > 0 and miles_travelled > 0:
#                 efficiency = miles_travelled / total_energy_used
#                 self._attr_state = round(efficiency, 2)

#                 _LOGGER.info(
#                     f"Continuous Efficiency Updated: {miles_travelled:.2f} miles / {total_energy_used:.2f} kWh = {self._attr_state:.2f} mi/kWh"
#                 )

#         # Update tracking variables for the next calculation
#         if is_moving:
#             self.last_miles = miles_now
#             self.last_energy = total_energy_used if total_energy_used is not None else self.last_energy
#             self.last_soc = battery_level

#         return self._attr_state