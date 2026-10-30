import sys
import os
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import sys_config
from app.core.collector import TelemetryCollector, SensorSource
from app.core.detector import GameDetector
from app.core.controller import ThermalController
from app.core.engine import DecisionEngine

def test_sensor_abstraction():
    print("\n--- 1. Testing Sensor Abstraction & TelemetryCollector ---")
    collector = TelemetryCollector(force_simulation=True)
    metrics = collector.collect()
    
    assert "cpu_temp" in metrics, "Missing cpu_temp"
    assert "temperature_source" in metrics, "Missing temperature_source"
    assert "temperature_backend" in metrics, "Missing temperature_backend"
    assert metrics["temperature_source"] in [SensorSource.REAL_HARDWARE.value, SensorSource.SIMULATION.value], f"Invalid source: {metrics['temperature_source']}"
    print(f"  [OK] Telemetry: Temp={metrics['cpu_temp']}°C, Source={metrics['temperature_source']}, Backend={metrics['temperature_backend']}")

    # Manual testing override check
    collector.set_override_temperature(92.5)
    temp, source, backend = collector.get_cpu_temp()
    assert temp == 92.5, f"Expected override 92.5°C, got {temp}"
    assert backend == "Manual Testing Override", f"Expected backend 'Manual Testing Override', got '{backend}'"
    collector.set_override_temperature(None)
    print("  [OK] Sensor manual override working.")

def test_configurable_detector():
    print("\n--- 2. Testing Configurable GameDetector ---")
    detector = GameDetector()
    
    # Assert formatting
    detector.set_mock_gaming(True, "cs2.exe")
    assert detector.get_formatted_status() == "GAMING: YES — cs2.exe"
    detector.set_mock_gaming(False)
    
    # Custom game addition & persistence
    test_game = "test_custom_game_runner.exe"
    detector.add_target_game(test_game)
    assert test_game in sys_config.get_game_list()
    
    detector.remove_target_game(test_game)
    assert test_game not in sys_config.get_game_list()
    print("  [OK] Configurable game list add/remove and persistence functional.")

def test_controller_safety_and_restoration():
    print("\n--- 3. Testing ThermalController Safety & Restoration ---")
    controller = ThermalController(dry_run_override=True)
    status = controller.get_status()
    
    assert "power_plan" in status
    assert "original_plan_guid" in status
    assert "original_cpu_max_state" in status
    assert status["dry_run"] is True
    
    # Unchanged state skip verification
    controller.current_plan = "balanced"
    skipped = controller.set_power_plan("balanced")
    assert skipped is True
    
    # Original configuration restoration
    restored = controller.restore_original_configuration()
    assert restored is True
    print("  [OK] ThermalController original state capture, unchanged skip, and restoration functional.")

def test_engine_thresholds_and_safety_overrides():
    print("\n--- 4. Testing Hybrid Decision Engine Thresholds & Safety Overrides ---")
    engine = DecisionEngine(hysteresis_seconds=0) # 0s for immediate testing
    now = time.time()
    
    # 70°C, Non-gaming -> Balanced, 100% CPU
    d1 = engine.evaluate({"cpu_temp": 70.0}, predicted_temp=72.0, is_gaming=False, current_time=now)
    assert d1["mode"] == "balanced" and d1["cpu_limit"] == 100, f"Failed 70°C non-gaming: {d1}"
    
    # 70°C, Gaming -> Performance, 100% CPU
    d2 = engine.evaluate({"cpu_temp": 70.0}, predicted_temp=75.0, is_gaming=True, current_time=now)
    assert d2["mode"] == "performance" and d2["cpu_limit"] == 100, f"Failed 70°C gaming: {d2}"
    
    # 80°C boundary -> Balanced, 100% CPU
    d3 = engine.evaluate({"cpu_temp": 75.0}, predicted_temp=80.0, is_gaming=True, current_time=now)
    assert d3["mode"] == "balanced" and d3["cpu_limit"] == 100, f"Failed 80°C: {d3}"

    # 89°C boundary -> Balanced, 100% CPU
    d4 = engine.evaluate({"cpu_temp": 82.0}, predicted_temp=89.0, is_gaming=True, current_time=now)
    assert d4["mode"] == "balanced" and d4["cpu_limit"] == 100, f"Failed 89°C: {d4}"

    # 90°C boundary -> Balanced, 99% CPU (Boost reduction)
    d5 = engine.evaluate({"cpu_temp": 85.0}, predicted_temp=90.0, is_gaming=True, current_time=now)
    assert d5["mode"] == "balanced" and d5["cpu_limit"] == 99, f"Failed 90°C: {d5}"

    # 94°C boundary -> Balanced, 99% CPU
    d6 = engine.evaluate({"cpu_temp": 88.0}, predicted_temp=94.0, is_gaming=True, current_time=now)
    assert d6["mode"] == "balanced" and d6["cpu_limit"] == 99, f"Failed 94°C: {d6}"

    # 95°C boundary -> Saver, 85% CPU (Emergency cooling)
    d7 = engine.evaluate({"cpu_temp": 89.0}, predicted_temp=95.0, is_gaming=True, current_time=now)
    assert d7["mode"] == "saver" and d7["cpu_limit"] == 85, f"Failed 95°C: {d7}"

    # 100°C boundary -> Saver, 85% CPU
    d8 = engine.evaluate({"cpu_temp": 92.0}, predicted_temp=100.0, is_gaming=True, current_time=now)
    assert d8["mode"] == "saver" and d8["cpu_limit"] == 85, f"Failed 100°C: {d8}"

    # Safety Override Test: Forecast says 72°C, but Actual Temp is 96°C -> MUST trigger emergency saver 85%
    d_safe = engine.evaluate({"cpu_temp": 96.0}, predicted_temp=72.0, is_gaming=True, current_time=now)
    assert d_safe["mode"] == "saver" and d_safe["cpu_limit"] == 85, f"Safety Override failed: {d_safe}"
    assert d_safe["emergency_override"] is True, "Emergency override flag not set"
    print("  [OK] DecisionEngine thresholds (70°C to 100°C) and Emergency Safety Overrides verified.")

def test_hysteresis_suppression():
    print("\n--- 5. Testing Hysteresis Transition Suppression ---")
    engine = DecisionEngine(hysteresis_seconds=10) # 10s hysteresis
    now = time.time()
    
    # 1st step: Set initial mode to Performance
    engine.evaluate({"cpu_temp": 70.0}, predicted_temp=72.0, is_gaming=True, current_time=now)
    
    # 2nd step (2 seconds later): Forecast rises to 85°C (suggests Balanced), but hysteresis (10s) blocks transition
    d_hyst = engine.evaluate({"cpu_temp": 72.0}, predicted_temp=85.0, is_gaming=True, current_time=now + 2.0)
    assert d_hyst["hysteresis_blocked"] is True, "Hysteresis block flag should be True"
    assert d_hyst["mode"] == "performance", f"Expected performance (blocked), got {d_hyst['mode']}"
    print("  [OK] Hysteresis correctly suppressed rapid transition.")

def main():
    print("==========================================================")
    print("=== RUNNING EXTENDED SYSTEM CORE TEST SUITE (test_core.py) ===")
    print("==========================================================")
    test_sensor_abstraction()
    test_configurable_detector()
    test_controller_safety_and_restoration()
    test_engine_thresholds_and_safety_overrides()
    test_hysteresis_suppression()
    print("\n[SUCCESS] ALL SYSTEM CORE TESTS PASSED 100%!")

if __name__ == "__main__":
    main()
