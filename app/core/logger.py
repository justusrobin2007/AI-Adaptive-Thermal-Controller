import os
import csv
import logging
from datetime import datetime

logger = logging.getLogger("ThermalController.Logger")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
CSV_PATH = os.path.join(DATA_DIR, "thermal_log.csv")

# Full expanded CSV schema
HEADERS = [
    "timestamp",
    "cpu_temp",
    "gpu_temp",
    "temperature_source",
    "cpu_usage",
    "gpu_usage",
    "ram_usage",
    "cpu_freq_mhz",
    "is_gaming",
    "game_name",
    "predicted_temp",
    "prediction_type",
    "selected_mode",
    "cpu_limit",
    "power_plan",
    "action_taken",
    "emergency_override",
    "hysteresis_blocked",
    "controller_status"
]

def _migrate_csv_headers():
    """Migrates existing thermal_log.csv to include gpu_temp and gpu_usage if needed."""
    if os.path.exists(CSV_PATH) and os.path.getsize(CSV_PATH) > 0:
        try:
            with open(CSV_PATH, "r", encoding="utf-8") as f:
                header_line = f.readline().strip()
            if "gpu_temp" not in header_line:
                import pandas as pd
                df = pd.read_csv(CSV_PATH)
                if "gpu_temp" not in df.columns:
                    df["gpu_temp"] = ""
                if "gpu_usage" not in df.columns:
                    df["gpu_usage"] = ""
                for col in HEADERS:
                    if col not in df.columns:
                        df[col] = ""
                df = df[HEADERS]
                df.to_csv(CSV_PATH, index=False)
                logger.info("Migrated thermal_log.csv headers to include GPU telemetry.")
        except Exception as e:
            logger.debug(f"CSV header migration notice: {e}")

_migrate_csv_headers()

def log_data(data_dict: dict) -> bool:
    """
    Appends a telemetry & decision record to data/thermal_log.csv.
    Automatically creates directories and writes headers if file does not exist.
    """
    try:
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR, exist_ok=True)
            logger.info(f"Created logging directory: {DATA_DIR}")

        file_exists = os.path.exists(CSV_PATH)
        
        # Format timestamp if epoch float passed
        raw_ts = data_dict.get("timestamp", datetime.now())
        if isinstance(raw_ts, (int, float)):
            formatted_ts = datetime.fromtimestamp(raw_ts).strftime("%Y-%m-%d %H:%M:%S")
        else:
            formatted_ts = str(raw_ts)

        # Build complete row matching HEADERS
        row = {
            "timestamp": formatted_ts,
            "cpu_temp": data_dict.get("cpu_temp", ""),
            "gpu_temp": data_dict.get("gpu_temp", ""),
            "temperature_source": data_dict.get("temperature_source", "SIMULATION"),
            "cpu_usage": data_dict.get("cpu_usage", data_dict.get("cpu_util", "")),
            "gpu_usage": data_dict.get("gpu_usage", data_dict.get("gpu_util", "")),
            "ram_usage": data_dict.get("ram_usage", data_dict.get("ram_util", "")),
            "cpu_freq_mhz": data_dict.get("cpu_freq_mhz", 2800),
            "is_gaming": data_dict.get("is_gaming", False),
            "game_name": data_dict.get("game_name", "None"),
            "predicted_temp": data_dict.get("predicted_temp", ""),
            "prediction_type": data_dict.get("prediction_type", "HEURISTIC / FALLBACK"),
            "selected_mode": data_dict.get("selected_mode", data_dict.get("mode", "")),
            "cpu_limit": data_dict.get("cpu_limit", 100),
            "power_plan": data_dict.get("power_plan", "balanced"),
            "action_taken": data_dict.get("action_taken", ""),
            "emergency_override": data_dict.get("emergency_override", False),
            "hysteresis_blocked": data_dict.get("hysteresis_blocked", False),
            "controller_status": data_dict.get("controller_status", "ACTIVE")
        }

        # Check existing CSV header compatibility
        write_header = not file_exists or os.path.getsize(CSV_PATH) == 0

        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS, extrasaction="ignore")
            if write_header:
                writer.writeheader()
                logger.info(f"Initialized new thermal logfile with expanded schema: {CSV_PATH}")
            writer.writerow(row)
            
        return True
    except Exception as e:
        logger.error(f"Failed to log telemetry to CSV: {e}")
        return False
