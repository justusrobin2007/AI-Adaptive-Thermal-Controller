# AI Adaptive Thermal Controller

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6.svg)](https://microsoft.com/windows)
[![UI](https://img.shields.io/badge/UI-Streamlit%20%26%20Plotly-FF4B4B.svg)](https://streamlit.io/)
[![ML](https://img.shields.io/badge/Model-Random%20Forest%20Regressor-orange.svg)](https://scikit-learn.org/)
[![Architecture](https://img.shields.io/badge/Architecture-Modular%20%26%20Decoupled-brightgreen.svg)]()

> **Predictive Windows Thermal Management & Performance Optimization System**  
> Proactively manages thermal loads on gaming laptops and desktops by anticipating CPU temperature spikes 10 seconds into the future using machine learning and dynamically tuning Windows power schemes before hardware throttling occurs.

---

## 📌 Overview & Problem Statement

Modern gaming laptops and high-performance desktops frequently suffer from **thermal throttling**:
* **The Problem:** Standard OS and BIOS cooling algorithms are *reactive*. They wait until temperatures hit $95^\circ\text{C}-100^\circ\text{C}$ before engaging fans or abruptly slashing clock speeds, resulting in stutter, micro-freezes, and long-term hardware degradation.
* **The Solution:** The **AI Adaptive Thermal Controller** acts *proactively*. It continuously collects telemetry (CPU/RAM utilization, CPU frequency, active game processes), predicts temperatures ~10 seconds into the future ($t + 10\text{s}$) using a Random Forest model, and modulates Windows power schemes and processor performance states (`powercfg`) to stabilize thermals smoothly.

---

## 🏛️ System Architecture

The project follows the **Single Responsibility Principle (SRP)** with modular, loosely coupled components:

```
                                [ HARDWARE LAYER ]
                (Windows Kernel PDH | LibreHardwareMonitor | Dynamic Simulator)
                                        │
                                        ▼
                            [ app/core/collector.py ]
                     Reads CPU/RAM utilization, frequency & temperatures
                                        │
                       ┌────────────────┴────────────────┐
                       ▼                                 ▼
           [ app/core/detector.py ]             [ app/core/ml_model.py ]
          Detects active game processes        Forecasts temp 10s into future
                       │                                 │
                       └────────────────┬────────────────┘
                                        ▼
                            [ app/core/engine.py ]
                    Hybrid Decision Engine + Hysteresis Cooldown
                                        │
                                        ▼
                          [ app/core/controller.py ]
                    Applies Windows powercfg & CPU State Caps
                                        │
                       ┌────────────────┴────────────────┐
                       ▼                                 ▼
             [ data/thermal_log.csv ]             [ dashboard.py ]
              Appends system telemetry        Live Streamlit Web Dashboard
```

---

## ⚡ Key Features

### 1. Multi-Tier Sensor Abstraction & Transparency
* **Zero-Admin Kernel Access**: Native Windows Kernel Performance Data Helper (PDH) queries thermal zones with no third-party software and zero elevated permissions needed.
* **Direct Silicon Diode**: Automatically queries **LibreHardwareMonitor** WMI or local web server for exact CPU die sensor temperatures.
* **Dynamic Thermodynamic Fallback**: If sensors are locked by OEM BIOS (e.g. certain proprietary laptop motherboards), it seamlessly falls back to a thermodynamic simulation model and explicitly tags all readings as `SIMULATION`.

### 2. Machine Learning Temperature Forecasting
* **Algorithm**: `RandomForestRegressor` trained on real-time and historical telemetry.
* **Time-Series Integrity**: Strict chronological validation split (first 80% train, latest 20% validation) to eliminate time-series data leakage.
* **Timestamp Delta Lookahead**: Dynamically pairs data points across actual timestamp deltas ($\Delta t \ge 8.0\text{s}$) to predict target temperature 10 seconds ahead.
* **Continual Learning**: Telemetry is logged continuously, and the model retrains asynchronously on a background thread every 60 seconds without stalling the main control loop.

### 3. Hybrid Decision Engine & Dual-Layer Safety
1. **Proactive Layer (ML Forecast)**:
   * **$< 80^\circ\text{C}$**: `Performance` (if gaming detected) or `Balanced` (100% CPU limit).
   * **$80^\circ\text{C} - 90^\circ\text{C}$**: `Balanced` mode (100% CPU limit).
   * **$90^\circ\text{C} - 95^\circ\text{C}$**: `Balanced` mode with **99% CPU limit** (disables aggressive CPU Turbo Boost, dropping temperatures by 10–15°C with negligible gaming FPS impact).
   * **$\ge 95^\circ\text{C}$**: `Power Saver` mode with **85% CPU limit** (emergency rapid cooling).
2. **Immutable Physical Safety Override**: Regardless of ML predictions, if physical hardware temperature hits $\ge 95^\circ\text{C}$, the system immediately triggers emergency cooling.
3. **Hysteresis Smoothing**: Enforces a 10-second transition cooldown to eliminate rapid oscillations ("hunting") between power plans.

### 4. Guaranteed Hardware State Restoration
* Upon startup, the controller queries and preserves your exact original Windows power plan GUID and processor state cap.
* On graceful exit (`q`, Ctrl+C, or `stop.bat`), the system **guarantees complete restoration** of your computer's original power settings.

---

## 📁 Repository Structure

```text
AI-Adaptive-Thermal-Controller/
├── .gitignore                     # Git ignore rules (clean repository standard)
├── config.json                    # Central configuration for thresholds, limits & games
├── dashboard.py                   # Interactive Streamlit & Plotly web dashboard
├── main.py                        # Central orchestrator loop (polls every 2.0s)
├── run.bat                        # Master one-click startup batch script
├── start.bat                      # Quick launch shortcut
├── stop.bat                       # Graceful service shutdown & power state reset
├── run_experiment.py              # Baseline vs. Adaptive scientific experiment script
├── test_core.py                   # Automated test suite for sensors, detector & controller
├── test_ai.py                     # Automated test suite for ML forecaster & CSV logger
├── requirements.txt               # Python package dependencies
├── PROJECT_GUIDE.md               # Detailed technical and architectural reference guide
├── README.md                      # Primary project documentation
├── app/
│   ├── __init__.py
│   └── core/
│       ├── __init__.py
│       ├── collector.py           # Multi-tier sensor telemetry extractor (PDH/WMI)
│       ├── config.py              # Thread-safe configuration manager singleton
│       ├── controller.py          # Windows powercfg actuator & state restorer
│       ├── detector.py            # Active gaming process scanner
│       ├── engine.py              # Hybrid decision engine & hysteresis rules
│       ├── logger.py              # Telemetry CSV data logger with auto-migration
│       ├── ml_model.py            # Chronological Random Forest ML forecaster
│       └── simulation.py          # Dynamic thermodynamic load simulator
├── data/
│   └── thermal_log.csv            # Telemetry records for warm-start model training
└── tools/
    └── LibreHardwareMonitor/      # Embedded sensor bridge for real CPU diode reads
```

---

## 🚀 Quick Start Guide

### Prerequisites
* **Operating System**: Windows 10 or Windows 11 (64-bit).
* **Python**: Version 3.10 or higher ([Download Python](https://www.python.org/downloads/)).
* *Note: Administrator rights are recommended to allow `powercfg` adjustments and hardware sensor reads. Without admin rights, the system safely defaults to Dry-Run / Simulation mode.*

### Option A: One-Click Launch (Recommended)
Simply double-click **`run.bat`** (or right-click &rarr; *Run as administrator*).

`run.bat` automatically:
1. Detects your Python environment and installs any missing dependencies.
2. Starts the background hardware sensor monitor.
3. Launches the **Streamlit Web Dashboard** at `http://localhost:8501`.
4. Starts the **Main Controller Loop** in your terminal.

> **To Stop:** Press `q` or `Ctrl+C` in the terminal, or run **`stop.bat`** to instantly restore standard Windows power plans.

---

### Option B: Manual Command-Line Execution

1. **Clone the repository:**
   ```bash
   git clone https://github.com/justusrobin2007/AI-Adaptive-Thermal-Controller.git
   cd AI-Adaptive-Thermal-Controller
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the Controller Loop:**
   ```bash
   python main.py
   ```

4. **Start the Web Dashboard (in a separate terminal):**
   ```bash
   streamlit run dashboard.py
   ```

---

## 🧪 Testing & Verification

The project includes unit, boundary-value, and integration test suites:

```bash
# Run core system tests (sensors, power controller, safety limits)
python test_core.py

# Run ML and data pipeline tests (chronological split, fallback, CSV schema)
python test_ai.py
```

### Running Scientific Benchmarks
To compare default Windows thermal behavior against the adaptive controller:
```bash
python run_experiment.py
```

---

## ⚙️ Configuration (`config.json`)

You can customize thermal thresholds, processor percentage limits, and your target game list directly in [`config.json`](file:///c:/Users/ROG/.gemini/antigravity/scratch/thermal_controller/config.json):

```json
{
  "game_list": [
    "cyberpunk2077.exe",
    "cs2.exe",
    "valorant.exe",
    "gta5.exe",
    "eldenring.exe"
  ],
  "thresholds": {
    "cool_threshold": 80.0,
    "balanced_threshold": 90.0,
    "boost_reduction_threshold": 95.0,
    "emergency_threshold": 95.0
  },
  "cpu_limits": {
    "normal_cpu_limit": 100,
    "boost_reduced_cpu_limit": 99,
    "emergency_cpu_limit": 85
  },
  "hysteresis_seconds": 10
}
```

---

## 📊 Streamlit Web Dashboard

The web dashboard (`http://localhost:8501`) provides:
* **Real-Time Telemetry Gauges**: Dual CPU & GPU temperature gauges showing actual sensor origin (`REAL_HARDWARE` vs `SIMULATION`).
* **Live Forecast Chart**: Interactive Plotly time-series comparing actual temperature with the 10-second ML prediction overlay.
* **Control History Log**: Real-time table documenting state transitions, CPU limit adjustments, and emergency interventions.
* **Thermal Stress Scenarios**: Built-in scenario simulator (`RAPID_SPIKE`, `EMERGENCY_CRISIS`, `GAMING_LOAD`) to verify controller responses safely.

---

## ⚖️ License & Attribution
Developed for educational, research, and performance optimization purposes. LibreHardwareMonitor components are licensed under the Mozilla Public License 2.0 (MPL-2.0).
