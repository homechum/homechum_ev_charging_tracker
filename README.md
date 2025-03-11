# HomeChum EV Charging Tracker

A custom Home Assistant integration to track and analyze EV charging sessions using data from Ohme, Volkswagen Connect, and Octopus Energy, with support for manual logging of public charging sessions.

## Features
- **Efficiency Metrics:** Calculates miles per 1% SOC (with caching during charging) and miles per kWh.
- **Cost Analysis:** Computes charging cost per session, optimal charging cost, and potential savings.
- **Manual Input Aggregation:** Stores and aggregates manual public charging session data.
- **Persistent Storage:** Uses Home Assistant’s storage helper to save public charging sessions.
- **Custom Service:** Provides a service (`homechum_ev_charging_tracker.log_public_charging`) to log manual public charging sessions.
- **Public Charging Detection:** Binary sensor to detect when a public charging session is in use.

## Installation
1. Copy the `homechum_ev_charging_tracker` folder to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Configure required input entities (such as `input_number.myida_start_mile` and `input_number.myida_start_soc`) and sensors in your Home Assistant setup.
4. Use the custom service to log public charging sessions:
   ```yaml
   service: homechum_ev_charging_tracker.log_public_charging
   data:
     provider: "ChargePoint"
     kwh: 15.5
     cost: 3.0
     miles: 25
