import sys
import os
import time
import pandas as pd
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.logger import log_data, CSV_PATH
from app.core.ml_model import TemperaturePredictor
from app.core.engine import DecisionEngine

def test_logger_schema():
    print("\n--- 1. Testing Expanded CSV Logger Schema ---")
    if os.path.exists(CSV_PATH):
        try:
            os.remove(CSV_PATH)
        except Exception:
            pass

    log_entry = {
        "timestamp": time.time(),
        "cpu_temp": 76.4,
        "temperature_source": "REAL_HARDWARE",
        "cpu_usage": 45.0,
        "ram_usage": 60.0,
        "cpu_freq_mhz": 3200.0,
        "is_gaming": True,
        "game_name": "cyberpunk2077.exe",
        "predicted_temp": 82.1,
        "prediction_type": "ML FORECAST",
        "selected_mode": "balanced",
        "cpu_limit": 100,
        "power_plan": "balanced",
        "action_taken": "Testing logger",
        "emergency_override": False,
        "hysteresis_blocked": False,
        "controller_status": "ACTIVE"
    }

    succ = log_data(log_entry)
    assert succ is True, "log_data failed"
    assert os.path.exists(CSV_PATH), "CSV file was not created"

    df = pd.read_csv(CSV_PATH)
    assert len(df) == 1
    assert "temperature_source" in df.columns
    assert "prediction_type" in df.columns
    assert df.iloc[0]["temperature_source"] == "REAL_HARDWARE"
    assert df.iloc[0]["game_name"] == "cyberpunk2077.exe"
    print("  [OK] Logger written with expanded schema.")

def test_ml_forecaster_and_evaluation():
    print("\n--- 2. Testing ML Forecaster, Chronological Split & Fallback ---")
    predictor = TemperaturePredictor()

    # 1. Fallback Test (Small dataset)
    pred_val, pred_type = predictor.predict_temp({"cpu_temp": 75.0, "cpu_usage": 50.0, "ram_usage": 60.0, "is_gaming": True})
    assert isinstance(pred_val, float)
    assert pred_type == "HEURISTIC / FALLBACK", f"Expected 'HEURISTIC / FALLBACK', got '{pred_type}'"
    print(f"  [OK] Fallback estimator: {pred_val}°C ({pred_type})")

    # 2. Write 35 mock records with 2-second timestamp increments to simulate sequential logs
    print("  Populating CSV with 35 sequential telemetry frames (~10s horizon test)...")
    base_ts = time.time() - 100
    for i in range(35):
        log_data({
            "timestamp": base_ts + (i * 2.0),
            "cpu_temp": 50.0 + i * 1.1,
            "temperature_source": "SIMULATION",
            "cpu_usage": 30.0 + i * 1.4,
            "ram_usage": 45.0 + i * 0.4,
            "cpu_freq_mhz": 2800 + i * 20,
            "is_gaming": True if i > 15 else False,
            "game_name": "cs2.exe" if i > 15 else "None",
            "predicted_temp": 52.0 + i * 1.1,
            "prediction_type": "HEURISTIC / FALLBACK",
            "selected_mode": "balanced",
            "cpu_limit": 100,
            "power_plan": "balanced",
            "action_taken": "Populating dataset",
            "emergency_override": False,
            "hysteresis_blocked": False,
            "controller_status": "ACTIVE"
        })

    # 3. Train RandomForest model
    train_success = predictor.train_model()
    assert train_success is True, "RandomForest training failed"
    assert predictor.is_trained is True

    stats = predictor.get_model_stats()
    assert stats["is_trained"] is True
    assert stats["prediction_type"] == "ML FORECAST"
    assert stats["mae"] is not None
    assert stats["rmse"] is not None
    print(f"  [OK] Trained ML model evaluated on chronological validation split: MAE={stats['mae']}°C, RMSE={stats['rmse']}°C, R²={stats['r2']}")

    # 4. Predict with trained model
    pred_ml, pred_ml_type = predictor.predict_temp({"cpu_temp": 80.0, "cpu_usage": 60.0, "ram_usage": 65.0, "is_gaming": True, "cpu_freq_mhz": 3200})
    assert isinstance(pred_ml, float)
    assert pred_ml_type == "ML FORECAST", f"Expected 'ML FORECAST', got '{pred_ml_type}'"
    print(f"  [OK] ML Prediction: {pred_ml}°C ({pred_ml_type})")

def main():
    print("==========================================================")
    print("=== RUNNING EXTENDED AI TEST SUITE (test_ai.py) ===")
    print("==========================================================")
    test_logger_schema()
    test_ml_forecaster_and_evaluation()
    print("\n[SUCCESS] ALL AI TESTS PASSED 100%!")

if __name__ == "__main__":
    main()
