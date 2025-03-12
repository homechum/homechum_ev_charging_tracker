# **HomeChum EV Charging Tracker - Home Assistant Custom Component**

A custom Home Assistant integration to track and analyze EV charging sessions using data from Ohme, Volkswagen Connect, and Octopus Energy, with support for manual logging of public charging sessions.

## **📌 Overview**
This custom component enhances Home Assistant by tracking **EV charging efficiency, energy usage, cost, and savings**. The sensors provide insights into **miles/kWh efficiency, charging costs, energy consumed, and idle losses**.

---

## **⚙️ Installation Instructions**
### **Prerequisites**
1. **Home Assistant Installed** (Core, Supervised, or OS version)
2. **A Supported EV Integration** (e.g., `volkswagen Connect`, `ohme`, `octopus energy`)
3. **HACS (Home Assistant Community Store)** - Recommended for easy updates
4. Add input_number to configuration.yaml
    ```yaml
    input_number:
      ev_public_charge_cost_per_kwh:
        name: Public Charging Cost per kWh
        min: 0
        max: 5
        step: 0.01
        unit_of_measurement: "GBP/kWh"
        mode: box


### **Manual Installation**
1. Download the custom component files.
2. Place them inside the following directory:
   ```
   /config/custom_components/homechum_ev_charging_tracker/
   ```
3. Restart Home Assistant.
4. Add the integration via **Settings > Devices & Services**.
5. Restart Home Assistant again to load all sensors.

### **Installation via HACS (Recommended)**
1. Open **HACS** in Home Assistant.
2. Navigate to **Integrations** and click **"+"**.
3. Search for `EV Efficiency & Charging Sensors`.
4. Click **"Install"** and restart Home Assistant.
5. Configure sensors via **Settings > Devices & Services**.

---

## **📖 List of Sensors**
### **🔹 Charging Efficiency Sensors**
| Sensor Name | Purpose | Attributes |
|-------------|---------|------------|
| `sensor.ev_charge_to_charge_efficiency` | Calculates miles/kWh efficiency between charge cycles | `Miles/kWh` |
| `sensor.ev_drive_to_drive_efficiency` | Calculates miles/kWh efficiency between drive cycles | `Miles/kWh` |
| `sensor.ev_continuous_efficiency` | Continuously tracks real-time miles/kWh efficiency | `Miles/kWh` |

### **🔹 Charging Energy Sensors**
| Sensor Name | Purpose | Attributes |
|-------------|---------|------------|
| `sensor.ev_home_energy_per_charge` | Tracks home charging session energy usage | `kWh per session` |
| `sensor.ev_public_energy_per_session` | Tracks public charging session energy usage | `kWh per session` |
| `sensor.ev_total_home_energy` | Accumulates total home charging energy | `Total kWh used at home` |
| `sensor.ev_total_public_energy` | Accumulates total public charging energy | `Total kWh used at public chargers` |

### **🔹 Charging Cost Sensors**
| Sensor Name | Purpose | Attributes |
|-------------|---------|------------|
| `sensor.ev_home_charge_cost_per_session` | Tracks home charging cost per session | `GBP per session` |
| `sensor.ev_total_home_charge_cost` | Accumulates total home charging cost | `Total GBP spent on home charging` |
| `sensor.ev_public_charge_cost_per_session` | Tracks public charging cost per session | `GBP per session` |
| `sensor.ev_total_public_charge_cost` | Accumulates total public charging cost | `Total GBP spent on public charging` |

### **🔹 Savings Sensors**
| Sensor Name | Purpose | Attributes |
|-------------|---------|------------|
| `sensor.ev_home_charge_savings_per_session` | Calculates cost savings for each home charging session | `GBP saved per session` |
| `sensor.ev_total_home_charge_savings` | Tracks total home charging savings compared to Octopus Energy rates | `Total GBP saved` |

### **🔹 Efficiency Sensors (Miles/kWh)**
| Sensor Name | Purpose | Attributes |
|-------------|---------|------------|
| `sensor.ev_charge_to_charge_miles_per_kwh` | Tracks charge-to-charge efficiency in miles/kWh | `Miles/kWh` |
| `sensor.ev_drive_to_drive_miles_per_kwh` | Tracks drive-to-drive efficiency in miles/kWh | `Miles/kWh` |
| `sensor.ev_continuous_miles_per_kwh` | Tracks real-time continuous efficiency in miles/kWh | `Miles/kWh` |

### **🔹 Special Condition Sensors**
| Sensor Name | Purpose | Attributes |
|-------------|---------|------------|
| `sensor.ev_idle_energy_loss` | Tracks energy loss while the car is idle (not moving) | `Total kWh lost while idle` |
| `sensor.ev_public_charging_detected` | Detects when the vehicle is using a public charger | `On/Off` |

---

## **🔍 How Sensors Work**
### **Charging Efficiency Calculation**
- **`ChargeToChargeMilesPerKWhSensor`** calculates miles/kWh after each **full charge cycle**.
- **`DriveToDriveMilesPerKWhSensor`** calculates efficiency for **each drive session**.
- **`ContinuousMilesPerKWhSensor`** updates efficiency **in real-time** while driving.

### **Charging Cost Tracking**
- **For Home Charging:** Uses either **fixed rate (0.07 GBP/kWh)** or **dynamic Octopus tariff**.
- **For Public Charging:** Requires **user input** for cost per kWh.
- **Total cost is accumulated over time.**

### **Energy Loss Detection**
- **Idle Energy Loss (`sensor.ev_idle_energy_loss`)** detects when SoC drops without movement.
- **Public Charging Detection (`sensor.ev_public_charging_detected`)** ensures public energy usage is tracked separately.

---

## **📊 Dashboards & Automations**
Once installed, use the following in **Lovelace**:
### **Example Lovelace Card (Efficiency & Cost Tracking)**
```yaml
entities:
  - entity: sensor.ev_charge_to_charge_miles_per_kwh
    name: Charge-to-Charge Efficiency
  - entity: sensor.ev_drive_to_drive_miles_per_kwh
    name: Drive-to-Drive Efficiency
  - entity: sensor.ev_continuous_miles_per_kwh
    name: Real-Time Efficiency
  - entity: sensor.ev_total_home_charge_cost
    name: Total Home Charging Cost
  - entity: sensor.ev_total_public_charge_cost
    name: Total Public Charging Cost
  - entity: sensor.ev_total_home_charge_savings
    name: Total Home Charging Savings
  - entity: sensor.ev_idle_energy_loss
    name: Idle Energy Loss
```

### **Automations**
- **Notify when a charge session ends:** Prompt user to enter public charging cost.
- **Track monthly charging trends:** Summarize total cost and efficiency.
- **Compare smart charge vs. normal charge savings**.

---

## **🎯 Future Improvements**
1. **Monthly & Yearly Reports for Charging Cost & Efficiency** 📆
2. **Historical Trend Tracking (Best & Worst Efficiency)** 📊
3. **Rolling 30-Day Average Miles/kWh Tracker** 📈

🚀 **This integration helps you optimize EV charging, reduce costs, and improve efficiency!**
