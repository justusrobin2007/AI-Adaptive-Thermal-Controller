import sys
import os
import time
import logging
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.collector import TelemetryCollector
from app.core.detector import GameDetector
from app.core.controller import ThermalController
from app.core.engine import DecisionEngine
from app.core.ml_model import TemperaturePredictor
from app.core.simulation import SCENARIOS, SimulationScenarioRunner

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("ExperimentRunner")

def run_experiment_session(mode_name: str, duration_sec: int = 30) -> list:
    """
    Executes a controlled simulation session under a specified control mode.
    
    Args:
        mode_name (str): 'BASELINE' (no intervention) or 'ADAPTIVE_CONTROLLER'
        duration_sec (int): Duration of the simulation run in seconds.
        
    Returns:
        list of telemetry & decision dict records.
    """
    logger.info(f"Starting Experiment Session: {mode_name} (Duration: {duration_sec}s)")
    
    collector = TelemetryCollector(force_simulation=True)
    detector = GameDetector()
    controller = ThermalController(dry_run_override=True)
    engine = DecisionEngine(hysteresis_seconds=4)
    predictor = TemperaturePredictor()
    
    detector.set_mock_gaming(True, "cyberpunk2077.exe")
    
    # Train predictor if data exists
    predictor.train_model()
    
    records = []
    start_time = time.time()
    loop_count = 0
    
    while (time.time() - start_time) < duration_sec:
        loop_start = time.time()
        loop_count += 1
        
        # Simulate load escalation over time
        elapsed = loop_start - start_time
        sim_load = min(98.0, 30.0 + (elapsed / duration_sec) * 65.0)
        collector.override_temp = 50.0 + (elapsed / duration_sec) * 48.0
        
        telemetry = collector.collect()
        telemetry["cpu_util"] = round(sim_load, 1)
        is_gaming, game_name = detector.check_is_gaming()
        
        predicted_temp, pred_type = predictor.predict_temp(telemetry)
        
        if mode_name == "BASELINE":
            # No control actions taken; lock at 100% CPU limit and Balanced plan
            target_plan = "balanced"
            target_cpu_limit = 100
            decision = {
                "mode": "balanced",
                "cpu_limit": 100,
                "reason": "BASELINE MODE (No Intervention)",
                "emergency_override": False,
                "hysteresis_blocked": False
            }
        else: # ADAPTIVE_CONTROLLER
            decision = engine.evaluate(telemetry, predicted_temp, is_gaming, loop_start)
            target_plan = decision["mode"]
            target_cpu_limit = decision["cpu_limit"]
            
            # Apply simulated controller state changes
            controller.set_power_plan(target_plan)
            controller.set_cpu_max_state(target_cpu_limit)

        records.append({
            "timestamp": loop_start,
            "mode_name": mode_name,
            "cpu_temp": telemetry["cpu_temp"],
            "cpu_util": telemetry["cpu_util"],
            "predicted_temp": predicted_temp,
            "target_plan": target_plan,
            "target_cpu_limit": target_cpu_limit,
            "emergency_override": decision.get("emergency_override", False),
            "hysteresis_blocked": decision.get("hysteresis_blocked", False)
        })
        
        time.sleep(1.0)
        
    return records

def calculate_metrics(records: list) -> dict:
    df = pd.DataFrame(records)
    if df.empty:
        return {}

    temps = df["cpu_temp"].values
    times = df["timestamp"].values
    
    max_temp = round(float(np.max(temps)), 1)
    avg_temp = round(float(np.mean(temps)), 1)
    
    # Temperature rise rate (°C per second)
    temp_delta = temps[-1] - temps[0]
    time_delta = max(1.0, times[-1] - times[0])
    rise_rate = round(float(temp_delta / time_delta), 2)
    
    # Time spent above 90C
    time_above_90 = round(float(np.sum(temps >= 90.0) * 1.0), 1)
    
    # Mode transitions
    plan_changes = np.sum(df["target_plan"].values[:-1] != df["target_plan"].values[1:])
    limit_changes = np.sum(df["target_cpu_limit"].values[:-1] != df["target_cpu_limit"].values[1:])
    total_transitions = int(plan_changes + limit_changes)

    return {
        "max_temp": max_temp,
        "avg_temp": avg_temp,
        "rise_rate": rise_rate,
        "time_above_90": time_above_90,
        "total_transitions": total_transitions
    }

def main():
    print("\n" + "="*70)
    print("=== AI ADAPTIVE THERMAL CONTROLLER: SCIENTIFIC EXPERIMENT RUNNER ===")
    print("="*70)
    
    duration = 20
    print(f"\n1. Executing BASELINE Session (Standard Windows Default Power Management) [{duration}s]...")
    base_records = run_experiment_session("BASELINE", duration_sec=duration)
    base_metrics = calculate_metrics(base_records)

    print(f"\n2. Executing ADAPTIVE CONTROLLER Session (Proactive AI Thermal Control) [{duration}s]...")
    adapt_records = run_experiment_session("ADAPTIVE_CONTROLLER", duration_sec=duration)
    adapt_metrics = calculate_metrics(adapt_records)

    print("\n" + "="*70)
    print("=== EXPERIMENTAL EVALUATION REPORT SUMMARY ===")
    print("="*70)
    
    print(f"{'Metric':<32} | {'Baseline (No Control)':<22} | {'Adaptive AI Controller':<22}")
    print("-" * 80)
    print(f"{'Maximum Temperature (°C)':<32} | {base_metrics.get('max_temp', 0):<22} | {adapt_metrics.get('max_temp', 0):<22}")
    print(f"{'Average Temperature (°C)':<32} | {base_metrics.get('avg_temp', 0):<22} | {adapt_metrics.get('avg_temp', 0):<22}")
    print(f"{'Temperature Rise Rate (°C/s)':<32} | {base_metrics.get('rise_rate', 0):<22} | {adapt_metrics.get('rise_rate', 0):<22}")
    print(f"{'Time Above 90°C (sec)':<32} | {base_metrics.get('time_above_90', 0):<22} | {adapt_metrics.get('time_above_90', 0):<22}")
    print(f"{'Controller Transitions':<32} | {base_metrics.get('total_transitions', 0):<22} | {adapt_metrics.get('total_transitions', 0):<22}")
    print("="*80 + "\n")

    # Thermal reduction conclusions
    temp_reduction = round(base_metrics.get("max_temp", 0) - adapt_metrics.get("max_temp", 0), 1)
    time_saved = round(base_metrics.get("time_above_90", 0) - adapt_metrics.get("time_above_90", 0), 1)
    
    print(f"CONCLUSION: The Adaptive Thermal Controller reduced peak CPU temperature by {temp_reduction}°C and reduced critical thermal exposure (>90°C) by {time_saved} seconds.")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
