# AI Adaptive Thermal Controller - Project Guide

## 1) Project purpose

This project is a Windows-focused thermal management and performance optimization system. It monitors CPU temperature, CPU usage, RAM usage, and active game processes, predicts future temperature trends, and then adjusts Windows power settings and CPU maximum state to keep the system cool without unnecessary throttling.

The project is designed to:

- read live hardware telemetry
- detect when the user is gaming
- predict near-future heat buildup using a machine learning model
- apply cooling actions using Windows power plans and CPU limits
- log decisions to CSV for analysis
- visualize live telemetry and model behavior in a Streamlit dashboard

The objective is not simply to monitor heat; it actively tries to keep hardware under safe thermal conditions while maintaining acceptable performance for gaming sessions.

---

## 2) High-level system behavior

The runtime loop in main.py does the following every ~2 seconds:

1. Collects telemetry:
   - CPU utilization
   - RAM utilization
   - CPU temperature
   - timestamp
2. Detects whether an active game process is running
3. Uses a temperature predictor to estimate what the CPU temperature will be 10 seconds ahead
4. Evaluates the current state with a decision engine
5. Changes Windows power plan and CPU max state as needed
6. Logs the decision and telemetry to CSV
7. Prints console status
8. Re-trains the ML model periodically in the background

This creates a feedback loop: telemetry -> prediction -> cooling decision -> hardware adjustment -> logging -> dashboard update.

---

## 3) Project structure

```text
thermal_controller/
├── main.py
├── dashboard.py
├── requirements.txt
├── PROJECT_GUIDE.md
├── data/
│   └── thermal_log.csv
├── app/
│   ├── __init__.py
│   └── core/
│       ├── __init__.py
│       ├── collector.py
│       ├── controller.py
│       ├── detector.py
│       ├── engine.py
│       ├── logger.py
│       └── ml_model.py
├── test_core.py
├── test_ai.py
└── README-like notes (if any in the project root)
```

## 4) Key files and responsibilities

### main.py
This is the main application launcher and control loop.

Responsibilities:

- imports all core components
- creates the collector, detector, controller, engine, and predictor objects
- initializes training data if logs exist
- starts the user input monitor thread
- repeatedly polls telemetry and applies decisions
- logs every cycle
- restores default system settings when the program exits

Important functions:

- user_input_loop(detector, collector, stop_event)
  - listens to console input
  - supports commands like:
    - g on
    - g off
    - t 92
    - t auto
    - q / exit
  - used for manual simulation and testing

- retrain_model_background(predictor)
  - runs a background model retrain without blocking the main loop

- main()
  - orchestrates the full system lifecycle
  - runs the main telemetry loop
  - updates power plans and CPU limits
  - logs output and triggers retraining periodically

### dashboard.py
This is the monitoring visual interface built with Streamlit.

Responsibilities:

- reads the CSV telemetry file
- converts log data to a dashboard
- displays latest metrics and charts
- visualizes CPU temperature, CPU usage, RAM usage, and AI forecast vs actual
- auto-refreshes the UI every 2 seconds

It is not the main control system; it is a reporting layer based on the same CSV logs that the main loop writes.

### app/core/collector.py
This is the telemetry collection layer.

Responsibilities:

- collect system metrics
- query CPU/RAM hardware state
- query temperature via WMI when available
- fall back to a simulated thermal model when WMI is not accessible

Important functions:

- __init__()
  - initializes WMI connection if available
  - tries to detect whether temperature readings can come from native Windows sensors
  - enables mock thermal mode if WMI cannot be used

- get_cpu_utilization()
  - uses psutil.cpu_percent(interval=None)
  - if psutil is missing, returns a random simulated value

- get_ram_utilization()
  - uses psutil.virtual_memory().percent
  - otherwise returns a simulated value

- get_cpu_temp()
  - if override_temp is set, returns it directly
  - otherwise tries to read WMI sensor values from root\wmi
  - reads the CurrentTemperature field from MSAcpi_ThermalZoneTemperature
  - converts decikelvin to Celsius using:
    - temp_c = (CurrentTemperature / 10.0) - 273.15
  - if WMI fails, uses _simulate_temperature()

- _simulate_temperature()
  - creates a load-aware thermal model
  - target temperature rises with CPU load
  - uses inertia to smooth spikes
  - adds minor random fluctuations
  - clamps values between realistic limits

- collect()
  - returns a single dictionary with:
    - timestamp
    - cpu_util
    - ram_util
    - cpu_temp

### app/core/detector.py
This module detects whether a game is active.

Responsibilities:

- monitors process names
- compares running executable names against a hardcoded set of known games
- returns True if a target executable is running

Important functions:

- __init__(custom_games=None)
  - initializes target_games with known process names such as:
    - rdr2.exe
    - valorant.exe
    - cyberpunk2077.exe
    - gta5.exe
    - cs2.exe
    - overwatch.exe
    - leagueoflegends.exe
    - fortniteclient-win64-shipping.exe
    - eldenring.exe
    - skyrim.exe

- check_is_gaming()
  - loops through psutil.process_iter(attrs=['name'])
  - checks each process name against the target list
  - if a match is found, returns (True, process_name)

- add_target_game(process_name)
  - adds a custom monitoring name

- remove_target_game(process_name)
  - removes a custom game name

- set_mock_gaming(status, mock_name)
  - used for manual testing of gaming state without launching actual game processes

### app/core/controller.py
This module controls the computer’s power policy.

Responsibilities:

- switch Windows power plans
- set CPU maximum processor state
- check whether the app is running with admin privileges
- execute safe subprocess commands with powercfg

Important constants:

- GUIDS = {
  - "balanced": "381b4222-f694-41f0-9685-ff5bb260df2e",
  - "performance": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
  - "saver": "a1841308-3541-4fab-bc81-f71556f20b4a"
  }

Important functions:

- _check_admin_rights()
  - checks whether the script is running with administrator privileges on Windows

- _run_command(cmd)
  - runs subprocess commands safely
  - returns status and output
  - in dry-run mode it simulates success when admin rights / Windows environment are unavailable

- set_power_plan(plan_name)
  - calls:
    - powercfg -setactive <guid>
  - sets the active Windows power plan

- set_cpu_max_state(percent)
  - calls powercfg to set maximum processor state for AC and DC power
  - uses the Windows setting called PROCTHROTTLEMAX
  - accepts values between 50 and 100
  - values such as 99% disable turbo-style boost behavior

- get_status()
  - returns current power plan, CPU limit, admin status, and whether the platform is Windows

### app/core/engine.py
This is the decision engine that decides how aggressive the thermal management should be.

Responsibilities:

- combine predicted temperature and current temperature
- decide whether to stay on balanced/performance/saver
- enforce hysteresis so the system does not rapidly oscillate between plans

Important logic:

- if predicted_temp < 80C:
  - performance plan if gaming
  - otherwise balanced
  - CPU limit = 100

- if 80 <= predicted_temp < 90:
  - balanced
  - CPU limit = 100

- if 90 <= predicted_temp < 95:
  - balanced
  - CPU limit = 99

- if predicted_temp >= 95:
  - saver
  - CPU limit = 85

Safety override:

- if current temperature >= 95C, force saver mode and 85% CPU limit
- if current temperature >= 90C, force balanced mode and 99% CPU limit

Hysteresis:

- prevents rapid switching between power plans by gating control changes for several seconds
- tracks the last transition time
- avoids constant power-plan thrashing

### app/core/ml_model.py
This module builds and runs the predictive model.

Responsibilities:

- train a RandomForestRegressor using historical logs
- predict the temperature 10 seconds into the future
- if training data is not available or model fails, fall back to a heuristic thermal approximation

Important constants:

- CSV_DIR = project data folder
- CSV_PATH = data/thermal_log.csv

Important functions:

- __init__()
  - sets up the model and feature list
  - features = ["cpu_temp", "cpu_usage", "ram_usage", "is_gaming"]

- train_model()
  - loads CSV telemetry from thermal_log.csv
  - requires at least 25 rows before training
  - converts types and cleans missing data
  - maps is_gaming values to 0/1
  - targets the future temperature by shifting the CPU temp column back by 5 time steps
    - because each polling cycle is about 2 seconds
    - 5 steps corresponds to around 10 seconds ahead
  - trains a RandomForestRegressor with 30 trees and shallow depth

- predict_temp(current_state_dict)
  - takes current values like CPU temp, CPU usage, RAM usage, and gaming status
  - if trained, runs the regressor
  - if not trained, uses fallback physical estimation

Fallback predictor logic:

- heavy load increases predicted temperature
- low load reduces predicted temperature
- gaming adds a bonus increase
- predictions are clamped to realistic bounds

### app/core/logger.py
This module handles CSV logging.

Responsibilities:

- create the data directory if it does not exist
- initialize CSV headers if file is missing
- append each telemetry record

Important constant:

- HEADERS = ["timestamp", "cpu_temp", "cpu_usage", "ram_usage", "is_gaming", "action_taken"]

Important function:

- log_data(data_dict)
  - writes a CSV row containing the current telemetry and the action string selected by the engine
  - ensures the file uses Windows-safe newline handling

---

## 5) Data sources and where readings come from

### CPU temperature
Primary source:

- Windows WMI namespace: root\wmi
- WMI class: MSAcpi_ThermalZoneTemperature
- field used: CurrentTemperature

Calculation:

```python
temp_c = (zone.CurrentTemperature / 10.0) - 273.15
```

This is because the WMI sensor reports temperature in decikelvin.

Fallback:

- if WMI is inaccessible, lacks permissions, or returns no data
- the project uses a dynamic thermal simulation instead of actual sensor readings

### CPU utilization
Source:

- psutil.cpu_percent(interval=None)

This is taken from the current system CPU load.

Fallback:

- random simulated load if psutil is unavailable

### RAM utilization
Source:

- psutil.virtual_memory().percent

Fallback:

- simulated random range if psutil is unavailable

### Gaming detection
Source:

- psutil.process_iter(attrs=['name'])
- checks process executable names against a list of known games

Examples include:

- cyberpunk2077.exe
- valorant.exe
- gta5.exe
- cs2.exe
- overwatch.exe
- leagueoflegends.exe
- fortniteclient-win64-shipping.exe

### ML training data
Source:

- previously logged readings from data/thermal_log.csv

The model learns from historical telemetry rows and predicts temperature 10 seconds ahead.

---

## 6) Runtime loop detail

The central loop in main.py works roughly like this:

```python
while not stop_event.is_set():
    loop_start = time.time()
    telemetry = collector.collect()
    is_gaming, game_name = detector.check_is_gaming()

    state_dict = {
        "cpu_temp": telemetry["cpu_temp"],
        "cpu_usage": telemetry["cpu_util"],
        "ram_usage": telemetry["ram_util"],
        "is_gaming": is_gaming
    }

    predicted_temp = predictor.predict_temp(state_dict)

    decision = engine.evaluate(telemetry, predicted_temp, is_gaming, loop_start)

    target_plan = decision["mode"]
    target_cpu_limit = decision["cpu_limit"]

    controller.set_power_plan(target_plan)
    controller.set_cpu_max_state(target_cpu_limit)

    log_data(...)
    print status
    sleep for the remaining portion of 2 seconds
```

Important timings:

- telemetry polling interval is about 2 seconds
- future temperature prediction horizon is roughly 10 seconds
- model retrain is triggered every 30 loops, which is about 60 seconds

---

## 7) How the decision engine chooses actions

The engine is a hybrid system combining:

- thermal safety thresholds
- predicted future temperature
- gaming detection
- hysteresis prevention for plan switching

Behavior summary:

| Predicted temp | Decision | CPU limit |
|---|---|---|
| < 80C | Performance if gaming; otherwise Balanced | 100 |
| 80C to < 90C | Balanced | 100 |
| 90C to < 95C | Balanced with boost reduction | 99 |
| >= 95C | Saver mode | 85 |

Emergency override:

- if current temperature is above 95, the system bypasses all normal logic and forces saver mode
- if current temperature is above 90, it forces balanced mode and 99% CPU threshold

This ensures the system protects hardware even when the prediction model is uncertain or the machine is under stress.

---

## 8) How the model training works

The ML model is trained using the past recorded telemetry in thermal_log.csv.

The model uses these features:

- cpu_temp
- cpu_usage
- ram_usage
- is_gaming

The target is a shifted temperature value representing what the CPU temp will be 10 seconds later.

The code uses a RandomForestRegressor from scikit-learn with shallow trees to keep inference lightweight.

The training code:

- reads CSV logs
- ensures enough rows exist
- cleans invalid values
- converts booleans to 0/1
- shifts the target by 5 steps (2-second intervals -> roughly 10 seconds)
- trains the model
- stores it in self.model

If there is not enough data, the predictor falls back to a thermodynamic estimate instead of failing completely.

---

## 9) Logging format and data storage

Logs are stored in:

- data/thermal_log.csv

Columns:

- timestamp
- cpu_temp
- cpu_usage
- ram_usage
- is_gaming
- action_taken

Example row:

```csv
timestamp,cpu_temp,cpu_usage,ram_usage,is_gaming,action_taken
2026-09-25 12:00:00,72.2,58.3,41.0,True,"Set plan: PERFORMANCE & Set CPU limit: 100% (Proactive AI: Temp forecasted cool (76.8°C). Running PERFORMANCE (100% CPU).)"
```

The CSV is used both for:

- model retraining
- the Streamlit dashboard
- historical inspection and debugging

---

## 10) Dashboard functionality

The Streamlit dashboard reads the saved CSV file and displays:

- latest CPU temperature
- CPU utilization
- RAM utilization
- gaming status
- newest AI action log
- temperature timeline
- CPU/RAM usage graphs
- AI predicted vs actual charts

It does not actively control the system; it visualizes what the control loop already did.

Important dashboard behavior:

- if the log file does not exist, it shows a warning and waits for the controller to start logging
- it uses Plotly for rich charts
- it auto-reruns every 2 seconds

---

## 11) Dependencies

The project uses these libraries from requirements.txt:

- psutil
- pandas
- scikit-learn
- streamlit
- matplotlib
- plotly

These are used as follows:

- psutil -> system resource and process readings
- pandas -> CSV processing and training dataset preparation
- scikit-learn -> RandomForestRegressor model
- streamlit -> dashboard UI
- matplotlib -> plotting support (less central here)
- plotly -> visual charts in dashboard

---

## 12) Windows-specific design notes

This project is intentionally built around Windows behavior and tools:

- WMI is used for hardware temperature sensors
- powercfg is used to control active power plans and processor constraints
- administrator rights are required to reliably change CPU power settings

If the app is run without admin rights or on a non-Windows platform, the controller enters a dry-run or simulated mode and logs those changes without actually modifying the system.

---

## 13) Manual test commands supported by the app

The interactive input loop in main.py accepts these commands while the controller is running:

- g on
  - forces gaming mode on
- g off
  - disables gaming simulation
- t 92
  - manually overrides the CPU temperature to 92C
- t auto
  - restores automatic sensor/load-based telemetry
- q or exit
  - shuts the system down safely

These commands simplify testing without needing real hardware events or actual game launch.

---

## 14) Typical run flow

### Step 1: Install dependencies

```powershell
cd C:\path\to\thermal_controller
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Step 2: Run controller

```powershell
python main.py
```

### Step 3: Run dashboard

```powershell
streamlit run dashboard.py
```

The dashboard expects the control loop to have generated telemetry in data/thermal_log.csv.

---

## 15) Overall architecture summary

This project is a full closed-loop control system with four layers:

1. Sensing layer
   - collector.py reads CPU/RAM/temperature and game state

2. Prediction layer
   - ml_model.py predicts future temperature with a random forest

3. Decision layer
   - engine.py decides whether to keep balanced, performance, or saver mode

4. Control & visualization layer
   - controller.py applies OS-level hardware settings
   - dashboard.py visualizes logs

This is effectively a small embedded-style system: it observes physical conditions, predicts risk, then enforces safe operating limits in real time.

---

## 16) Important implementation takeaways

- The temperature reading is one of the most important runtime dependencies.
- If WMI fails, the app still works in simulation mode, but it is no longer reading real hardware temperature.
- The app assumes Windows because it directly uses powercfg and WMI.
- The model is trained from logged CSV data and is not a heavy deep learning system; it is intentionally lightweight and practical.
- The system is designed to be safe and less aggressive than a raw performance optimization app by using thermal thresholds and safety overrides.

---

## 17) Final summary

This project is a Windows-based AI thermal controller that monitors CPU telemetry, detects gaming activity, predicts future temperature spikes, and changes power settings automatically to manage thermal behavior. It takes readings from Windows WMI sensors for temperature and psutil for CPU/RAM usage, tracks process names to see if a game is running, builds a small RandomForest predictive model from historical log data, and then applies cooling actions through powercfg.

The app logs all telemetry and decisions to a CSV file and exposes a live dashboard for monitoring and analysis.
