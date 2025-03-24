"""Sensor platform for HomeChum EV Charging Tracker."""
import logging
import asyncio
from homeassistant.helpers.entity import Entity
from typing import Optional
from datetime import datetime
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)

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
    _LOGGER.info("HOMECHUM: Initializing EV Charging Tracker sensors")

    sensors = [
        ChargeToChargeEfficiencySensor(hass), #WORKING
        DriveToDriveEfficiencySensor(hass), #WORKING
        ContinuousEfficiencySensor(hass), #WORKING
        IdleSoCLossSensor(hass), #WORKING
        HomeEnergyConsumptionPerChargeSensor(hass),#WORKING
        AccumulateHomeEnergySensor(hass), #WORKING
        HomeChargeCostSensor(hass), #WORKING
        TotalHomeChargingCostSensor(hass),
        HomeChargingSavingsPerSessionSensor(hass),
        TotalHomeChargingSavingsSensor(hass),
        ChargeToChargeMilesPerKWhSensor(hass)
        # PublicEnergyConsumptionPerSessionSensor(hass),
        # TotalPublicEnergyConsumptionSensor(hass),
        # PublicChargingCostPerSessionSensor(hass),
        # TotalPublicChargingCostSensor(hass),
        # DriveToDriveMilesPerKWhSensor(hass)
    ]
    async_add_entities(sensors, update_before_add=True)

class ChargeToChargeEfficiencySensor(SensorEntity, RestoreEntity):
    """Sensor to track efficiency from charge to charge, restoring state on restart."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the efficiency sensor."""
        self.hass = hass
        self._attr_name = "EV Charge to Charge Efficiency"
        self._attr_unique_id = "ev_charge_to_charge_efficiency"
        self._attr_native_unit_of_measurement = "mi/%"
        self._attr_state: float = 0.0 # Start tracking from zero

        self.last_miles: float = 0.0
        self.last_soc: float = 0.0
        self.was_charging = False  # Flag to track if actual charging occurred

        _LOGGER.info("C2C Effcny: Initializing ChargeToChargeEfficiencySensor")

    def get_input_number_state(self, entity_id: str) -> float | None:
        """Retrieve a float value from an input_number entity in Home Assistant."""
        state = self.hass.states.get(entity_id)
        if state and state.state not in (None, "unknown", "unavailable"):
            try:
                return float(state.state)
            except ValueError:
                _LOGGER.warning("Invalid value stored in %s: %s", entity_id, state.state)
        return None
        
    async def async_added_to_hass(self):
        """Restore the last known efficiency value after a restart."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._attr_state = float(last_state.state)
                _LOGGER.info("C2C Effcny: Restored efficiency state: %s", self._attr_state)
            except ValueError:
                _LOGGER.warning("C2C Effcny: Stored state was invalid float: %s", last_state.state)

        _LOGGER.debug("C2C Effcny: Restoring stored last_miles and last_soc from input_numbers.")
        # self.last_miles = self.get_input_number_state("input_number.myida_c2c_start_mile") or 0.0
        # self.last_soc = self.get_input_number_state("input_number.myida_c2c_start_soc") or 0.0

        _LOGGER.debug("C2C Effcny: Subscribe to state changes for: %s", [
            "binary_sensor.myida_charging_cable_connected",
            "switch.myida_charging",
        ])
        # Subscribe to state changes using async_track_state_change_event.
        self._unsub = async_track_state_change_event(
            self.hass,
            ["binary_sensor.myida_charging_cable_connected", "switch.myida_charging"],
            self.async_update_callback
        )

    async def store_initial_values(self):
        """Store initial miles and SoC in Home Assistant input_number entities when charging starts."""
        miles_now = get_float_state(self.hass, "sensor.myida_odometer")
        soc_now = get_float_state(self.hass, "sensor.myida_battery_level")

        if miles_now is not None and soc_now is not None:
            await self.hass.services.async_call(
                "input_number", "set_value",
                {"entity_id": "input_number.myida_c2c_start_mile", "value": miles_now},
                blocking=True
            )
            await self.hass.services.async_call(
                "input_number", "set_value",
                {"entity_id": "input_number.myida_c2c_start_soc", "value": soc_now},
                blocking=True
            )
            _LOGGER.info("C2C Effcny: Stored initial values: last_miles=%s, last_soc=%s", miles_now, soc_now)
        else:
            _LOGGER.warning("C2C Effcny: Cannot store initial values: Odometer or battery level sensor unavailable.")
        
    async def async_will_remove_from_hass(self) -> None:
        """Cleanup when entity is about to be removed."""
        if hasattr(self, "_unsub") and self._unsub:
            self._unsub()
            self._unsub = None

    async def async_update_callback(self, event):
        """Triggered whenever the cable sensor or charging switch changes."""
        entity_id = event.data.get("entity_id")
        old_state_obj = event.data.get("old_state")
        new_state_obj = event.data.get("new_state")

        old_state = old_state_obj.state if old_state_obj else None
        new_state = new_state_obj.state if new_state_obj else None

        _LOGGER.debug(
            "C2C Effcny:: State change event for %s: %s → %s. Forcing sensor refresh.",
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
            _LOGGER.debug("C2C Effcny: Input signals not available: %s", self._attr_state)
            return self._attr_state

        cable_connected = (cable_state.state == "on")
        charging = (charging_state.state == "on")

        if cable_connected and charging:
            # Charging started: Mark this session as "charging detected"
            _LOGGER.debug("C2C Effcny: status of was_charging when EV charging started: %s", self.was_charging)
            if not self.was_charging:
                _LOGGER.debug("C2C Effcny: C2C Efficiency calcualtion started")
                miles_now = get_float_state(self.hass, "sensor.myida_odometer")
                _LOGGER.debug("C2C Effcny: C2C Efficiency calcualtion started miles_now: %s", miles_now)
                soc_now = get_float_state(self.hass, "sensor.myida_battery_level")
                _LOGGER.debug("C2C Effcny: C2C Efficiency calcualtion started Soc now: %s", soc_now)
                last_miles = self.get_input_number_state("input_number.myida_c2c_start_mile")
                _LOGGER.debug("C2C Effcny: C2C Efficiency calcualtion started last miles: %s", last_miles)
                last_soc = self.get_input_number_state("input_number.myida_c2c_start_soc")
                _LOGGER.debug("C2C Effcny: C2C Efficiency calcualtion started last soc: %s", last_soc)

                if None in (miles_now, soc_now, last_miles, last_soc):
                    _LOGGER.warning("C2C Effcny: Cannot calculate efficiency: Missing stored or current values.")
                    return self._attr_state

                miles_travelled = miles_now - last_miles
                soc_used = last_soc - soc_now

                if miles_travelled <= 0.1:  # Ensure the car actually moved
                    _LOGGER.warning("C2C Effcny: Drive cycle not detected (miles_travelled=%s). Skipping efficiency update.", miles_travelled)
                    return self._attr_state  # Prevent invalid calculations

                if soc_used > 0:
                    self._attr_state = round(miles_travelled / soc_used, 2)
                    _LOGGER.info("C2C Effcny: Updated efficiency: %s mi/%% (miles=%s, soc_used=%s)", self._attr_state, miles_travelled, soc_used)

                self.was_charging = True
                return self._attr_state  # Updated efficiency value
            return self._attr_state #Preserve previous value

        if not charging and not cable_connected and self.was_charging:
            # Cable unplugged after a successful charge → Calculate efficiency
            miles_now = get_float_state(self.hass, "sensor.myida_odometer")
            soc_now = get_float_state(self.hass, "sensor.myida_battery_level")
            _LOGGER.debug("C2C Effcny: status of was_charging when EV charging finished: %s", self.was_charging)

            # Store new values for the next charge cycle
            self.hass.async_create_task(self.store_initial_values())
            _LOGGER.info("C2C Effcny: One charging cycle complete and stored the current miles: %s and SoC: %s for next cycle", miles_now, soc_now)

            if miles_now is None or soc_now is None:
                _LOGGER.warning("C2C Effcny: Odometer or battery level sensor unavailable.")
                return self._attr_state
            _LOGGER.debug("C2C Effcny: Charging session complete and start miles recorded as = %s mi", miles_now)
            _LOGGER.debug("C2C Effcny: Charging session complete and start SoC recorded as = %s mi", soc_now)

            # Reset charging flag since charging session is complete
            self.was_charging = False
            return self._attr_state  # Keep updated efficiency value
            
        return self._attr_state  # Keep last efficiency value until next valid charge cycle

class DriveToDriveEfficiencySensor(SensorEntity, RestoreEntity):
    """Sensor to track drive-to-drive efficiency with a debounce to avoid quick stops."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Drive to Drive Efficiency"
        self._attr_unique_id = "ev_drive_to_drive_efficiency"
        self._attr_native_unit_of_measurement = "mi/%"
        self._attr_state: Optional[float] = 0.0

        # Track start conditions for each drive session
        self.start_miles: Optional[float] = None
        self.start_soc: Optional[float] = None

        # Keep reference to any scheduled "stop finalization" call
        self._stop_debounce_task = None

        _LOGGER.debug("D2DEffcny: DriveToDriveEfficiencySensor initialized.")

        # Listen for changes in the car’s “moving” state
        async_track_state_change_event(
            hass,
            ["binary_sensor.myida_vehicle_moving"],
            self.async_update_callback
        )

    async def async_added_to_hass(self):
        """Restore last known state on restart."""
        _LOGGER.info("D2DEffcny: DriveToDriveEfficiencySensor added to Home Assistant.")
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._attr_state = float(last_state.state)
                _LOGGER.debug("D2DEffcny: Restored drive-to-drive efficiency to %s", self._attr_state)
            except ValueError:
                _LOGGER.warning("D2DEffcny: Stored state was invalid float: %s", last_state.state)
                self._attr_state = 0.0

    async def async_update_callback(self, event):
        """
        Called when binary_sensor.myida_vehicle_moving changes.
        event.data includes entity_id, old_state, new_state, etc.
        """
        entity_id = event.data.get("entity_id")
        old_state_obj = event.data.get("old_state")
        new_state_obj = event.data.get("new_state")

        if not new_state_obj:
            return  # Unclear or missing new state

        moving = (new_state_obj.state == "on")
        _LOGGER.debug(
            "D2DEffcny: Movement state changed for %s: %s -> %s",
            entity_id,
            old_state_obj.state if old_state_obj else "unknown",
            new_state_obj.state
        )

        if moving:
            # Car just started moving again
            # Cancel any scheduled stop finalization
            if self._stop_debounce_task:
                _LOGGER.debug("D2DEffcny: Car restarted within grace; canceling stop finalization.")
                self._stop_debounce_task()
                self._stop_debounce_task = None

            # If we don't yet have a "start" condition, record it now
            if self.start_miles is None or self.start_soc is None:
                self.start_miles = get_float_state(self.hass, "sensor.myida_odometer")
                self.start_soc = get_float_state(self.hass, "sensor.myida_battery_level")
                _LOGGER.debug(
                    "D2DEffcny: Drive session started: miles=%.2f, soc=%.2f",
                    self.start_miles or 0,
                    self.start_soc or 0
                )

        else:
            # Car just stopped; schedule finalization
            _LOGGER.debug(
                "D2DEffcny: Car stopped; scheduling finalization in %s seconds.",
                DEBOUNCE_DELAY_SECONDS
            )
            if not self._stop_debounce_task:
                self._stop_debounce_task = async_call_later(
                    self.hass,
                    DEBOUNCE_DELAY_SECONDS,
                    self._finalize_stop
                )

        # Force sensor state refresh
        self.async_schedule_update_ha_state()

    @callback
    def _finalize_stop(self, _now):
        """
        Called after DEBOUNCE_DELAY_SECONDS if the car is still stopped.
        If the car moved in the meantime, we canceled this task, so
        we only get here if it truly stayed stopped.
        """
        self._stop_debounce_task = None

        # Check if car is still stopped
        moving_state = self.hass.states.get("binary_sensor.myida_vehicle_moving")
        if not moving_state or moving_state.state == "on":
            # Car restarted moving before grace time ended; do nothing
            _LOGGER.debug("D2DEffcny: Stop finalization called, but car already moving again.")
            return

        # Now we finalize the drive session
        miles_now = get_float_state(self.hass, "sensor.myida_odometer")
        soc_now = get_float_state(self.hass, "sensor.myida_battery_level")

        _LOGGER.debug(
            "D2DEffcny: Finalizing stop. Start miles=%s, start soc=%s, current miles=%s, current soc=%s",
            self.start_miles,
            self.start_soc,
            miles_now,
            soc_now
        )

        if (
            miles_now is not None and
            soc_now is not None and
            self.start_miles is not None and
            self.start_soc is not None and
            soc_now < self.start_soc
        ):
            soc_used = self.start_soc - soc_now
            miles_travelled = miles_now - self.start_miles
            if soc_used > 0:
                self._attr_state = round(miles_travelled / soc_used, 2)
                _LOGGER.info("D2DEffcny: Calculated new drive efficiency: %s mi/%%", self._attr_state)
        else:
            _LOGGER.debug("D2DEffcny: No valid usage/distance found, skipping update.")

        # Reset for the next drive session
        self.start_miles = None
        self.start_soc = None

        # Force an update to reflect final efficiency
        self.async_schedule_update_ha_state()

    @property
    def state(self) -> Optional[float]:
        """Return the most recent drive-to-drive efficiency."""
        return self._attr_state

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
                _LOGGER.warning("CEffcny: Stored state was invalid float: %s", last_state.state)
                self._attr_state = None

    async def async_update_callback(self, event):
        """Triggered when the battery level or charging switch changes. """
        entity_id = event.data.get("entity_id")
        _LOGGER.debug("CEffcny: State change event from %s. Scheduling efficiency update.", entity_id)

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
        _LOGGER.debug("IDLELoss: State change event from %s. Scheduling efficiency update.", entity_id)
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
        self.last_update = None  # Track last update time

    async def async_added_to_hass(self):
        """Restore previous charge session energy consumption after a restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            self._attr_state = float(last_state.state)

        # Register state change event listener without auto-removal
        self._unsub = async_track_state_change_event(
            self.hass,
            [
                "sensor.myida_charging_power",
                "switch.myida_charging",
                "binary_sensor.myida_charging_cable_connected",
                "binary_sensor.ev_public_charge_detected",
            ],
            self.async_update_callback,
        )
        
    async def async_will_remove_from_hass(self) -> None:
        """Cleanup when entity is about to be removed."""
        if hasattr(self, "_unsub") and self._unsub:
            self._unsub()
            self._unsub = None

    async def async_update_callback(self, event):
        entity_id = event.data.get("entity_id")
        _LOGGER.debug("HomeECpChrg: State change event from %s. starting update.", entity_id)
        """Triggered when charging power, charging state, cable connection, or public charge detection changes."""
        now = datetime.utcnow()
        if self.last_update:
            time_delta = (now - self.last_update).total_seconds() / 3600  # Convert seconds to hours
            charging_power = get_float_state(self.hass, "sensor.myida_charging_power")
            if charging_power is not None and charging_power > 0:
                self._attr_state += charging_power * time_delta  # kW * hours = kWh
                self._attr_state = max(0, self._attr_state)  # Prevent negative values
                self._attr_state = round(self._attr_state,2)
                _LOGGER.debug("HomeECpChrg: Updated energy consumption: %s kWh", self._attr_state)
        self.last_update = now
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):

        charging_power = get_float_state(self.hass, "sensor.myida_charging_power")
        charging_status = self.hass.states.get("switch.myida_charging")
        cable_connected = self.hass.states.get("binary_sensor.myida_charging_cable_connected")
        public_charging = self.hass.states.get("binary_sensor.public_charging_detected")

        if charging_power is None or charging_status is None or cable_connected is None or public_charging is None:
            self._attr_state = 0

            missing_inputs = []
            if charging_power is None:
                missing_inputs.append("sensor.myida_charging_power")
            if charging_status is None:
                missing_inputs.append("switch.myida_charging")
            if cable_connected is None:
                missing_inputs.append("binary_sensor.myida_charging_cable_connected")
            if public_charging is None:
                missing_inputs.append("binary_sensor.public_charging_detected")

            _LOGGER.warning("HomeECpChrg: Missing required sensor inputs: %s", ", ".join(missing_inputs))

            return round(self._attr_state, 2)  # Keep last recorded energy if data is unavailable

        charging = charging_status.state == "on"
        cable_plugged = cable_connected.state == "on"
        is_public_charging = public_charging.state == "on"

        if is_public_charging:
            # If public charging is detected, do not track home energy consumption
            _LOGGER.debug("HomeECpChrg: Public Charging Detected.")
            return self._attr_state

        # if charging and cable_plugged:
        #     """Triggered when charging power, charging state, cable connection, or public charge detection changes."""
        #     _LOGGER.debug("HomeECpChrg: Cable Pluged and Charging on. Lets do the Kwh calculation.")
        #     now = datetime.utcnow()
        #     if self.last_update:
        #         time_delta = (now - self.last_update).total_seconds() / 3600  # Convert seconds to hours
        #         charging_power = get_float_state(self.hass, "sensor.myida_charging_power")
        #         if charging_power is not None and charging_power > 0:
        #             self._attr_state += charging_power * time_delta  # kW * hours = kWh
        #             self._attr_state = max(0, self._attr_state)  # Prevent negative values
        #             self._attr_state = round(self._attr_state,2)
        #             _LOGGER.debug("HomeECpChrg: Updated energy consumption: %s kWh", self._attr_state)
        #     self.last_update = now
        #     return round(self._attr_state,2)

        # **RESET ENERGY TRACKING WHEN CHARGING SESSION ENDS**
        if not charging and not cable_plugged:
            #_LOGGER.debug("HomeECpChrg: Charging session ended. Resetting home energy consumption to 0.")
            self._attr_state = 0
            return round(self._attr_state,2)
            
        return round(self._attr_state,2)

class AccumulateHomeEnergySensor(SensorEntity, RestoreEntity):
    """
    Accumulate home energy usage (in kWh) from sensor.ev_home_energy_per_charge.

    Each time 'sensor.ev_home_energy_per_charge' changes, we calculate the difference
    between old_state and new_state. If new_state is bigger, we add that difference
    to our running total. This allows partial or incremental updates without double-counting.
    """

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "Total EV Home Energy"
        self._attr_unique_id = "ev_accumulate_home_energy"
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_state: float = 0.0

        _LOGGER.debug("HomeToTECpChrg: Initializing AccumulateHomeEnergySensor")
        
    async def async_added_to_hass(self):
        """Restore the previous total from the database on Home Assistant restart."""
        await super().async_added_to_hass()
        old_state = await self.async_get_last_state()
        if old_state and old_state.state not in ("unknown", "unavailable", None):
            try:
                self._attr_state = float(old_state.state)
                _LOGGER.info("HomeToTECpChrg: Restored accumulated total: %s kWh", self._attr_state)
            except ValueError:
                _LOGGER.warning("HomeToTECpChrg: Invalid stored total: %s", old_state.state)
        # Watch for changes in sensor.ev_home_energy_per_charge
        self._unsub = async_track_state_change_event(
            self.hass,
            ["sensor.ev_home_energy_per_charge"],
            self.async_energy_callback
        )
    
    async def async_will_remove_from_hass(self):
        """Called when entity is about to be removed."""
        # Clean up your subscriptions if needed
        if self._unsub:
            self._unsub()
            self._unsub = None

    async def async_energy_callback(self, event):
        """
        Called whenever sensor.ev_home_energy_per_charge changes.
        The event.data dict typically has "old_state" and "new_state".
        """
        old_state_obj = event.data.get("old_state")
        new_state_obj = event.data.get("new_state")

        if old_state_obj is None or new_state_obj is None:
            # We need both old & new to compute a difference.
            return
        old_val = float(old_state_obj.state)
        new_val = float(new_state_obj.state)
        diff = new_val - old_val

        # If the sensor increments or jumps upward, accumulate the difference.
        if diff > 0:
            self._attr_state += diff
            _LOGGER.debug(
                "HomeToTECpChrg: Energy sensor changed from %.2f kWh to %.2f kWh → added %.2f kWh. New total: %.2f kWh",
                old_val, new_val, diff, self._attr_state
            )
            self.async_schedule_update_ha_state(force_refresh=True)
        else:
            # If new_val <= old_val, likely a reset or no net increase;
            # we do not subtract from the total or do anything else.
            _LOGGER.debug(
                "HomeToTECpChrg: No net increase. Old=%.2f, New=%.2f; ignoring difference=%.2f",
                old_val, new_val, diff
            )

    @property
    def state(self) -> float:
        """Return the accumulated total kWh."""
        return round(self._attr_state, 2)

class HomeChargeCostSensor(SensorEntity, RestoreEntity):
    FIXED_RATE_GBP_PER_KWH = 0.07

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Home Charge Session Cost"
        self._attr_unique_id = "ev_home_charge_session_cost"
        self._attr_native_unit_of_measurement = "GBP"
        self._attr_state: float = 0.0

    async def async_added_to_hass(self):
        """When the entity is added to Home Assistant."""
        await super().async_added_to_hass()

        # Restore previous state if available
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._attr_state = float(last_state.state)
                _LOGGER.info("HomeCostpChrg: Restored cost sensor: £%s", self._attr_state)
            except ValueError:
                _LOGGER.warning("HomeCostpChrg: Could not parse restored cost: %s", last_state.state)

        # Subscribe to state-change events for the given entities
        self._unsub = async_track_state_change_event(
            self.hass,
            [
                "sensor.ev_home_energy_per_charge",
                "select.ohme_epod_charge_mode",
                "switch.myida_charging",
                "binary_sensor.myida_charging_cable_connected",
            ],
            self.async_update_callback
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup when entity is about to be removed."""
        if hasattr(self, "_unsub") and self._unsub:
            self._unsub()
            self._unsub = None
            
    async def async_update_callback(self, event):
        entity_id = event.data.get("entity_id")
        _LOGGER.debug("HomeCostpChrg: State change event for %s => recalc cost", entity_id)
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self) -> float | None:
        """Calculate and return the cost of the charge session."""
        
        # Get the charging status and cable connection state safely
        charging_status = self.hass.states.get("switch.myida_charging")
        cable_connected = self.hass.states.get("binary_sensor.myida_charging_cable_connected")

        if charging_status is None or cable_connected is None:
            _LOGGER.warning("HomeCostpChrg: One or more required sensors are unavailable. Returning None.")
            return self._attr_state  # Prevent crash if sensors are missing

        charging = charging_status.state == "on"
        cable_plugged = cable_connected.state == "on"

        # Determine rate per kWh
        if charging and cable_plugged and not self._was_charging:

            # Get energy consumption (ensure it's a float)
            energy_kwh = get_float_state(self.hass, "sensor.ev_home_energy_per_charge")
            if energy_kwh is None:
                _LOGGER.warning("HomeCostpChrg: Energy consumption sensor is unavailable. Returning None.")
                return self._attr_state

            # Get charging mode
            mode_obj = self.hass.states.get("select.ohme_epod_charge_mode")
            if not mode_obj or mode_obj.state in ("unknown", "unavailable"):
                mode = None
                _LOGGER.debug("HomeCostpChrg: Charging mode is unavailable.")
            else:
                mode = mode_obj.state

            if mode == "smart_charge":
                rate_gbp_per_kwh = self.FIXED_RATE_GBP_PER_KWH  # Assuming this is predefined
                # Store the current rate for future use
                self.last_rate_gbp_per_kwh = rate_gbp_per_kwh
            elif mode == "max_charge":
                rate_gbp_per_kwh = get_float_state(self.hass, "sensor.octopus_electricity_current_rate")
                # Store the current rate for future use
                self.last_rate_gbp_per_kwh = rate_gbp_per_kwh
            else:
                _LOGGER.debug("HomeCostpChrg: Mode is neither 'smart_charge' nor 'max_charge'. Keeping last known rate.")
                rate_gbp_per_kwh = getattr(self, "last_rate_gbp_per_kwh", None)  # Retrieve last stored value if available

            if rate_gbp_per_kwh is None:
                _LOGGER.warning("HomeCostpChrg: Electricity rate sensor is unavailable. Returning None.")
                return self._attr_state  # Prevent crash when rate is missing
            cost = energy_kwh * rate_gbp_per_kwh
            self._attr_state = round(cost, 2)
            return self._attr_state

        if not charging and not cable_plugged:
            #_LOGGER.debug("HomeCostpChrg: Charging session ended. Resetting home energy consumption to 0")
            self._attr_state = round(0,2)
            return self._attr_state

        _LOGGER.debug(
            "HomeCostpChrg: Computed cost = %s ",)

        return self._attr_state

class TotalHomeChargingCostSensor(SensorEntity, RestoreEntity):
    """Sensor to track total accumulated home charging cost across multiple sessions."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "Total Home Charging Cost"
        self._attr_unique_id = "ev_total_home_charge_cost"
        self._attr_native_unit_of_measurement = "GBP"
        self._attr_state: float = 0.0  # Start tracking from zero
        self.last_session_cost: float = 0.0  # Stores the last session cost

    async def async_added_to_hass(self):
        """Restore total home charging cost after a restart."""
        await super().async_added_to_hass()
        old_state = await self.async_get_last_state()
        if old_state and old_state.state not in ("unknown", "unavailable", None):
            try:
                self._attr_state = float(old_state.state)
                _LOGGER.info("HomeECToTCost: Restored accumulated total: %s £", self._attr_state)
            except ValueError:
                _LOGGER.warning("HomeECToTCost: Invalid stored total: %s", old_state.state)
        # Subscribe to state-change events for the given entities
        self._unsub = async_track_state_change_event(
            self.hass,
            [
                "sensor.ev_home_charge_session_cost",
            ],
            self.async_update_callback
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup when entity is about to be removed."""
        if hasattr(self, "_unsub") and self._unsub:
            self._unsub()
            self._unsub = None

    async def async_update_callback(self, event):
        """Triggered when a home charging session ends (cable unplugged or new cost is calculated)."""
        old_state_obj = event.data.get("old_state")
        new_state_obj = event.data.get("new_state")

        if old_state_obj is None or new_state_obj is None:
            # We need both old & new to compute a difference.
            return
        old_val = float(old_state_obj.state)
        new_val = float(new_state_obj.state)
        diff = new_val - old_val

        # If the sensor increments or jumps upward, accumulate the difference.
        if diff > 0:
            self._attr_state += diff
            _LOGGER.debug(
                "HomeECToTCost: Home energy cost per session changed from %.2f £ to %.2f £ → added %.2f £. New total: %.2f £",
                old_val, new_val, diff, self._attr_state
            )
            self.async_schedule_update_ha_state(force_refresh=True)
        else:
            # If new_val <= old_val, likely a reset or no net increase;
            # we do not subtract from the total or do anything else.
            _LOGGER.debug(
                "HomeECToTCost: No net increase. Old=%.2f £, New=%.2f £; ignoring difference=%.2f £",
                old_val, new_val, diff
            )

    @property
    def state(self):
        """Return the accumulated total kWh."""
        return round(self._attr_state, 2)

class HomeChargingSavingsPerSessionSensor(SensorEntity, RestoreEntity):
    """Sensor to calculate home charging savings per session compared to Octopus tariff."""
    FIXED_RATE_GBP_PER_KWH = 0.07

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV Home Charging Savings Per Session"
        self._attr_unique_id = "ev_home_charge_savings_per_session"
        self._attr_native_unit_of_measurement = "GBP"
        self._attr_state: float = 0.0  # Start tracking from zero

    async def async_added_to_hass(self):
        # Restore previous state if available
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._attr_state = float(last_state.state)
                _LOGGER.info("HomeSvngpChrg: Restored cost sensor: £%s", self._attr_state)
            except ValueError:
                _LOGGER.warning("HomeSvngpChrg: Could not parse restored cost: %s", last_state.state)

        self._unsub = async_track_state_change_event(
            self.hass,
            [
                "sensor.ev_home_charge_session_cost", 
                "sensor.ev_home_energy_per_charge",
                "binary_sensor.myida_charging_cable_connected",
                "switch.myida_charging",
            ],
            self.async_update_callback
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup when entity is about to be removed."""
        if hasattr(self, "_unsub") and self._unsub:
            self._unsub()
            self._unsub = None

    #async def async_update_callback(self, entity_id, old_state, new_state):
    async def async_update_callback(self, event):
        """Triggered when a home charging session ends."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        session_cost = get_float_state(self.hass, "sensor.ev_home_charge_session_cost")
        session_energy = get_float_state(self.hass, "sensor.ev_home_energy_per_charge")
        charging_status = self.hass.states.get("switch.myida_charging")
        octopus_rate = get_float_state(self.hass, "sensor.octopus_electricity_current_rate")
        cable_connected = self.hass.states.get("binary_sensor.myida_charging_cable_connected")
        public_charging = self.hass.states.get("binary_sensor.public_charging_detected")
        
        if session_cost is None or session_energy is None or octopus_rate is None or public_charging is None or cable_connected is None or charging_status is None:
            self._attr_state = 0
            missing_inputs = []
            if session_cost is None:
                missing_inputs.append("sensor.ev_home_charge_session_cost")
            if session_energy is None:
                missing_inputs.append("sensor.ev_home_energy_per_charge")
            if octopus_rate is None:
                missing_inputs.append("sensor.octopus_electricity_current_rate")
            if cable_connected is None:
                missing_inputs.append("binary_sensor.myida_charging_cable_connected")
            if public_charging is None:
                missing_inputs.append("binary_sensor.public_charging_detected")
            if charging_status is None:
                missing_inputs.append("sswitch.myida_charging")

            _LOGGER.warning("HomeSvngpChrg: Missing required sensor inputs: %s", ", ".join(missing_inputs))
            return round(self._attr_state, 2)  # Keep last recorded energy if data is unavailable

        charging = charging_status.state == "on"
        cable_plugged = cable_connected.state == "on"
        is_public_charging = public_charging.state == "on"

        if is_public_charging:
            # If public charging is detected, do not track home energy consumption
            _LOGGER.debug("HomeSvngpChrg: Public Charging Detected.")
            self._attr_state = round(0, 2)
            return self._attr_state

        # Calculate what the cost *would* have been at the full Octopus tariff
        if charging and cable_plugged:
            _LOGGER.debug("HomeSvngpChrg: Calculating the savings and so far: %s.", savings)
            normal_cost = session_energy * octopus_rate
            savings = normal_cost - session_cost  # Difference = savings
            self._attr_state = round(savings, 2)
            return self._attr_state

        if not charging and not cable_connected:
            #_LOGGER.debug("HomeSvngpChrg: Charging session completed and reseting the cost to 0.")
            self._attr_state = round(0, 2)
            return self._attr_state   # Prevent crash if sensors are missing
        
        return self._attr_state

class TotalHomeChargingSavingsSensor(SensorEntity, RestoreEntity):
    """Sensor to track total accumulated home charging savings compared to Octopus tariff."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "Total Home Charging Savings"
        self._attr_unique_id = "ev_total_home_charge_savings"
        self._attr_native_unit_of_measurement = "GBP"
        self._attr_state: float = 0.0  # Start tracking from zero

    async def async_added_to_hass(self):
        """Restore total home charging cost after a restart."""
        await super().async_added_to_hass()
        old_state = await self.async_get_last_state()
        if old_state and old_state.state not in ("unknown", "unavailable", None):
            try:
                self._attr_state = float(old_state.state)
                _LOGGER.info("HomeSvngToTCost: Restored accumulated total: %s £", self._attr_state)
            except ValueError:
                _LOGGER.warning("HomeSvngToTCost: Invalid stored total: %s", old_state.state)

        self._unsub = async_track_state_change_event(
            self.hass,
            [
                "sensor.ev_home_charge_savings_per_session",
            ],
            self.async_update_callback
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup when entity is about to be removed."""
        if hasattr(self, "_unsub") and self._unsub:
            self._unsub()
            self._unsub = None

    async def async_update_callback(self, event):
        """Triggered when a home charging session ends (cable unplugged or new cost is calculated)."""
        old_state_obj = event.data.get("old_state")
        new_state_obj = event.data.get("new_state")

        if old_state_obj is None or new_state_obj is None:
            # We need both old & new to compute a difference.
            return
        old_val = float(old_state_obj.state)
        new_val = float(new_state_obj.state)
        diff = new_val - old_val

        # If the sensor increments or jumps upward, accumulate the difference.
        if diff > 0:
            self._attr_state += diff
            _LOGGER.debug(
                "HomeECToTCost: Home energy cost per session changed from %.2f £ to %.2f £ → added %.2f £. New total: %.2f £",
                old_val, new_val, diff, self._attr_state
            )
            self.async_schedule_update_ha_state(force_refresh=True)
        else:
            # If new_val <= old_val, likely a reset or no net increase;
            # we do not subtract from the total or do anything else.
            _LOGGER.debug(
                "HomeECToTCost: No net increase. Old=%.2f £, New=%.2f £; ignoring difference=%.2f £",
                old_val, new_val, diff
            )

    @property
    def state(self):
        """Return the accumulated total savings."""
        return self._attr_state

class ChargeToChargeMilesPerKWhSensor(SensorEntity, RestoreEntity):
    """Sensor to calculate Charge-to-Charge efficiency in miles/kWh based on previous charge cycle."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "EV C2C Efficiency MipkWh"
        self._attr_unique_id = "ev_charge_to_charge_miles_per_kwh"
        self._attr_native_unit_of_measurement = "mi/kWh"
        self._attr_state: float = 0.0  # Efficiency starts as unknown
        
        self.last_miles: float = 0.0
        self.last_kwh: float = 0.0
        self.was_charging = False

    _LOGGER.info("C2C MilesPerKWh Effcny: Initializing ChargeToChargeEfficiencySensor")

    def get_input_number_state(self, entity_id: str) -> float | None:
        """Retrieve a float value from an input_number entity in Home Assistant."""
        state = self.hass.states.get(entity_id)
        if state and state.state not in (None, "unknown", "unavailable"):
            try:
                return float(state.state)
            except ValueError:
                _LOGGER.warning("C2C MilesPerKWh Effcny: Invalid value stored in %s: %s", entity_id, state.state)
        return None

    async def async_added_to_hass(self):
        """Restore the last known efficiency value after a restart."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._attr_state = float(last_state.state)
                _LOGGER.info("C2C MilespKWh: Restored efficiency state: %s", self._attr_state)
            except ValueError:
                _LOGGER.warning("C2C MilesPerKWh Effcny: Stored state was invalid float: %s", last_state.state)

        _LOGGER.debug("C2C MilesPerKWh Effcny: Restoring stored last_miles and last_kwh from input_numbers.")

        _LOGGER.debug("C2C MilesPerKWh Effcny: Subscribe to state changes for: %s", [
            "binary_sensor.myida_charging_cable_connected",
            "switch.myida_charging",
        ])

        # Subscribe to state changes using async_track_state_change_event.
        self._unsub = async_track_state_change_event(
            self.hass,
            ["binary_sensor.myida_charging_cable_connected", "switch.myida_charging"],
            self.async_update_callback
        )

    async def store_initial_values(self):
        """Store initial miles and SoC in Home Assistant input_number entities when charging starts."""
        # miles_now = get_float_state(self.hass, "sensor.myida_odometer")
        kwh_now = get_float_state(self.hass, "sensor.total_ev_home_energy")

        if kwh_now is not None:
            await self.hass.services.async_call(
                "input_number", "set_value",
                {"entity_id": "input_number.myida_c2c_start_kwh", "value": kwh_now},
                blocking=True
            )
            _LOGGER.info("C2C MilesPerKWh Effcny: Stored initial values: last_kwh=%s", kwh_now)
        else:
            _LOGGER.warning("C2C MilesPerKWh Effcny: Cannot store initial values: Odometer or Kwh sensor unavailable.")

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup when entity is about to be removed."""
        if hasattr(self, "_unsub") and self._unsub:
            self._unsub()
            self._unsub = None

    async def async_update_callback(self, event):
        """Triggered whenever the cable sensor or charging switch changes."""
        entity_id = event.data.get("entity_id")
        old_state_obj = event.data.get("old_state")
        new_state_obj = event.data.get("new_state")

        old_state = old_state_obj.state if old_state_obj else None
        new_state = new_state_obj.state if new_state_obj else None

        _LOGGER.debug(
            "C2C MilesPerKWh Effcny:: State change event for %s: %s → %s. Forcing sensor refresh.",
            entity_id, old_state, new_state
        )
        # Force an immediate update of our sensor
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def state(self):
        """Calculate and return the charge-to-charge miles/kwh efficiency."""
        cable_state = self.hass.states.get("binary_sensor.myida_charging_cable_connected")
        charging_state = self.hass.states.get("switch.myida_charging")

        if cable_state is None or charging_state is None:
            # Entities unavailable; keep the last known efficiency.
            _LOGGER.debug("C2C MilesPerKWh Effcny: Input signals not available: %s", self._attr_state)
            return self._attr_state

        cable_connected = (cable_state.state == "on")
        charging = (charging_state.state == "on")

        if cable_connected and charging:
            # Charging started: Mark this session as "charging detected"
            _LOGGER.debug("C2C MilesPerKWh Effcny: status of was_charging when EV charging started: %s", self.was_charging)
            if not self.was_charging:
                _LOGGER.debug("C2C MilesPerKWh Effcny: C2C Efficiency calcualtion started")
                miles_now = get_float_state(self.hass, "sensor.myida_odometer")
                _LOGGER.debug("C2C MilesPerKWh Effcny: C2C Efficiency calcualtion started miles_now: %s", miles_now)
                kwh_now = get_float_state(self.hass, "sensor.total_ev_home_energy")
                _LOGGER.debug("C2C MilesPerKWh Effcny: C2C Efficiency calcualtion started current kwh now: %s", kwh_now)
                last_miles = self.get_input_number_state("input_number.myida_c2c_start_mile")
                _LOGGER.debug("C2C MilesPerKWh Effcny: C2C Efficiency calcualtion started last miles: %s", last_miles)
                last_kwh = self.get_input_number_state("input_number.myida_c2c_start_kwh")
                _LOGGER.debug("C2C MilesPerKWh Effcny: C2C Efficiency calcualtion started last soc: %s", last_kwh)

                if None in (miles_now, kwh_now, last_miles, last_kwh):
                    _LOGGER.warning("C2C MilesPerKWh Effcny: Cannot calculate efficiency: Missing stored or current values.")
                    return self._attr_state

                miles_travelled = miles_now - last_miles
                kwh_used = last_kwh - kwh_now

                if miles_travelled <= 0.1:  # Ensure the car actually moved
                    _LOGGER.warning("C2C MilesPerKWh Effcny: Drive cycle not detected (miles_travelled=%s). Skipping efficiency update.", miles_travelled)
                    return self._attr_state  # Prevent invalid calculations

                if kwh_used > 0:
                    self._attr_state = round(miles_travelled / kwh_used, 2)
                    _LOGGER.info("C2C MilesPerKWh Effcny: Updated efficiency: %s mi/%% (miles=%s, kwh_used=%s)", self._attr_state, miles_travelled, kwh_used)

                self.was_charging = True
                return self._attr_state  # Updated efficiency value
            return self._attr_state #Preserve previous value

        if not charging and not cable_connected and self.was_charging:
            # Cable unplugged after a successful charge → Calculate efficiency
            miles_now = get_float_state(self.hass, "sensor.myida_odometer")
            kwh_now = get_float_state(self.hass, "sensor.total_ev_home_energy")
            _LOGGER.debug("C2C MilesPerKWh Effcny: status of was_charging when EV charging finished: %s", self.was_charging)

            # Store new values for the next charge cycle
            self.hass.async_create_task(self.store_initial_values())
            _LOGGER.info("C2C MilesPerKWh Effcny: One charging cycle complete and stored the current miles: %s and KWh: %s for next cycle", miles_now, kwh_now)

            if miles_now is None or kwh_now is None:
                _LOGGER.warning("C2C MilesPerKWh Effcny: Odometer or battery level sensor unavailable.")
                return self._attr_state
            _LOGGER.debug("C2C MilesPerKWh Effcny: Charging session complete and start miles recorded as = %s mi", miles_now)
            _LOGGER.debug("C2C MilesPerKWh Effcny: Charging session complete and start Kwh recorded as = %s KWh", kwh_now)

            # Reset charging flag since charging session is complete
            self.was_charging = False
            return self._attr_state  # Keep updated efficiency value
            
        return self._attr_state  # Keep last efficiency value until next valid charge cycle

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