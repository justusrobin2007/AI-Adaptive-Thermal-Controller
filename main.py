import sys
import os
import time
import atexit
import signal
import threading
import logging
from datetime import datetime

# Ensure App packages can be imported if script is executed directly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import sys_config
from app.core.collector import TelemetryCollector
from app.core.detector import GameDetector
from app.core.controller import ThermalController
from app.core.engine import DecisionEngine
from app.core.ml_model import TemperaturePredictor
from app.core.logger import log_data
from app.core.simulation import SimulationScenarioRunner

# Configure log output format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ThermalController.Main")

# Global handle for safe signal cleanup
g_controller = None

def cleanup_on_exit():
    """Restores user's original Windows power scheme & CPU limit on shutdown."""
    global g_controller
    if g_controller:
        logger.info("Executing graceful cleanup: Restoring original Windows power configuration...")
        g_controller.restore_original_configuration()
        logger.info("System clean shutdown completed successfully.")

def signal_handler(sig, frame):
    logger.info(f"Signal {sig} received. Initiating clean exit...")
    cleanup_on_exit()
    sys.exit(0)

def user_input_loop(detector: GameDetector, collector: TelemetryCollector, scenario_runner: SimulationScenarioRunner, stop_event: threading.Event):
    """Listens for stdin commands for interactive manual simulation and scenario testing."""
    time.sleep(1.0)
    print("\n" + "="*60)
    print("=== INTERACTIVE HARDWARE & SCENARIO SIMULATOR ACTIVE ===")
    print("Commands:")
    print("  'g on' [name] : Simulate game launch (e.g. 'g on cs2.exe')")
    print("  'g off'        : Stop gaming simulation")
    print("  't <deg>'      : Override CPU Temp (e.g. 't 92' or 't auto')")
    print("  'sc <key>'     : Load scenario (NORMAL_OFFICE, GAMING_LOAD, HEAVY_THERMAL_LOAD, RAPID_SPIKE, EMERGENCY_CRISIS, NONE)")
    print("  'q' or 'exit'  : Shutdown controller safely")
    print("="*60 + "\n")
    
    while not stop_event.is_set():
        try:
            line = sys.stdin.readline()
            if not line:
                break
            parts = line.strip().split()
            if not parts:
                continue
                
            cmd = parts[0].lower()
            if cmd in ("q", "exit"):
                logger.info("Termination instruction received. Initiating shutdown...")
                stop_event.set()
                break
            elif cmd == "g":
                if len(parts) > 1:
                    status = parts[1].lower()
                    if status == "on":
                        game_name = parts[2] if len(parts) > 2 else "cyberpunk2077.exe"
                        detector.set_mock_gaming(True, game_name)
                    elif status == "off":
                        detector.set_mock_gaming(False)
                    else:
                        print("Invalid parameter. Usage: 'g on <name>' or 'g off'")
                else:
                    print("Usage: 'g on <name>' or 'g off'")
            elif cmd == "t":
                if len(parts) > 1:
                    val = parts[1].lower()
                    if val == "auto":
                        collector.set_override_temperature(None)
                        logger.info("Restored automatic sensor temperature monitoring.")
                    else:
                        try:
                            temp_val = float(val)
                            collector.set_override_temperature(temp_val)
                            logger.info(f"Custom temperature testing override applied: {temp_val}°C")
                        except ValueError:
                            print("Invalid value. Usage: 't <number>' or 't auto'")
                else:
                    print("Usage: 't <number>' or 't auto'")
            elif cmd == "sc":
                if len(parts) > 1:
                    sc_key = parts[1].upper()
                    if sc_key in ("NONE", "RESET", "OFF"):
                        scenario_runner.set_scenario(None)
                    else:
                        scenario_runner.set_scenario(sc_key)
                else:
                    print("Available scenarios: NORMAL_OFFICE, GAMING_LOAD, HEAVY_THERMAL_LOAD, RAPID_SPIKE, EMERGENCY_CRISIS, NONE")
            else:
                print("Unknown command. Valid options: 'g on', 'g off', 't <deg>', 'sc <scenario>', 'q'")
        except Exception as e:
            logger.error(f"Error in command input handler: {e}")

def retrain_model_background(predictor: TemperaturePredictor):
    """Retrains Random Forest model asynchronously on a background thread."""
    logger.debug("Asynchronous background ML model retraining triggered...")
    predictor.train_model()

def main():
    global g_controller
    logger.info("Initializing AI Adaptive Thermal & Performance Controller System...")

    # Register exit and signal handlers for safe hardware restoration
    atexit.register(cleanup_on_exit)
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    except Exception:
        pass

    # Initialize Core Components
    collector = TelemetryCollector()
    detector = GameDetector()
    controller = ThermalController()
    g_controller = controller  # Assign global reference for cleanup
    
    engine = DecisionEngine()
    predictor = TemperaturePredictor()
    scenario_runner = SimulationScenarioRunner()

    # Initial synchronous model training if pre-existing logs are available
    predictor.train_model()

    stop_event = threading.Event()
    
    # Start command processing background thread
    input_thread = threading.Thread(
        target=user_input_loop,
        args=(detector, collector, scenario_runner, stop_event),
        daemon=True
    )
    input_thread.start()

    logger.info("AI Core Engine started. Polling loop active (every 2.0s).")
    
    loop_count = 0
    try:
        while not stop_event.is_set():
            loop_start = time.time()
            
            # 1. Check if a scenario is active, else collect telemetry
            sim_frame = scenario_runner.get_telemetry_frame()
            if sim_frame:
                telemetry = sim_frame
                is_gaming = sim_frame["is_gaming"]
                game_name = sim_frame["game_name"]
            else:
                telemetry = collector.collect()
                is_gaming, game_name = detector.check_is_gaming()
            
            # 2. Predict future temperature via ML
            predicted_temp, pred_type = predictor.predict_temp(telemetry)
            
            # 3. Evaluate Hybrid Decision Engine Rules
            decision = engine.evaluate(
                telemetry, 
                predicted_temp, 
                is_gaming, 
                loop_start
            )
            
            # 4. Check dynamic controller settings & Apply adjustments
            ctrl_cfg = sys_config.get_controller_settings()
            ctrl_enabled = ctrl_cfg.get("enabled", True)
            controller.dry_run = ctrl_cfg.get("dry_run", False) or not controller.is_windows or not controller.has_admin

            target_plan = decision["mode"]
            target_cpu_limit = decision["cpu_limit"]
            action_taken = "No change required"
            ctrl_status = controller.get_status()
            plan_changed = False
            cpu_limit_changed = False

            if not ctrl_enabled:
                action_taken = "Controller Paused (Monitoring Only)"
                ctrl_status_str = "PAUSED"
                # If previously throttled, restore unconstrained CPU state
                if ctrl_status["max_cpu_percent"] < 100:
                    controller.set_cpu_max_state(100)
            else:
                ctrl_status_str = "DRY_RUN" if ctrl_status["dry_run"] else "ACTIVE"
                plan_changed = ctrl_status["power_plan"] != target_plan
                cpu_limit_changed = ctrl_status["max_cpu_percent"] != target_cpu_limit

                if plan_changed or cpu_limit_changed:
                    actions = []
                    if plan_changed:
                        controller.set_power_plan(target_plan)
                        actions.append(f"Plan -> {target_plan.upper()}")
                    if cpu_limit_changed:
                        controller.set_cpu_max_state(target_cpu_limit)
                        actions.append(f"CPU Limit -> {target_cpu_limit}%")
                    action_taken = " & ".join(actions)

            # 5. Log Telemetry and Controls to CSV
            log_entry = {
                "timestamp": telemetry["timestamp"],
                "cpu_temp": telemetry["cpu_temp"],
                "gpu_temp": telemetry.get("gpu_temp", ""),
                "temperature_source": telemetry["temperature_source"],
                "cpu_usage": telemetry["cpu_util"],
                "gpu_usage": telemetry.get("gpu_util", ""),
                "ram_usage": telemetry["ram_util"],
                "cpu_freq_mhz": telemetry.get("cpu_freq_mhz", 2800),
                "is_gaming": is_gaming,
                "game_name": game_name or "None",
                "predicted_temp": predicted_temp,
                "prediction_type": pred_type,
                "selected_mode": target_plan,
                "cpu_limit": target_cpu_limit,
                "power_plan": ctrl_status.get("active_os_power_plan", ctrl_status["power_plan"]),
                "action_taken": action_taken,
                "emergency_override": decision["emergency_override"],
                "hysteresis_blocked": decision["hysteresis_blocked"],
                "controller_status": ctrl_status_str
            }
            log_data(log_entry)

            # 6. Concise & Formatted Console Output
            time_str = datetime.now().strftime("%H:%M:%S")
            src_tag = "REAL" if telemetry["temperature_source"] == "REAL_HARDWARE" else "SIMULATED"
            pred_tag = "ML" if pred_type == "ML FORECAST" else "FALLBACK"
            game_str = f"{game_name}" if is_gaming else "NO"
            
            gpu_str = ""
            if telemetry.get("gpu_temp") is not None:
                gpu_src = "REAL" if telemetry.get("gpu_source") == "REAL_HARDWARE" else "SIM"
                gpu_str = f" | GPU: {telemetry['gpu_temp']}°C ({gpu_src})"
            
            if decision["emergency_override"]:
                console_msg = f"[{time_str}] CRITICAL: CPU {telemetry['cpu_temp']}°C ({src_tag}){gpu_str} | Emergency Override -> {target_plan.upper()} / {target_cpu_limit}% CPU Limit"
            elif plan_changed or cpu_limit_changed:
                console_msg = f"[{time_str}] INTERVENTION: CPU {telemetry['cpu_temp']}°C ({src_tag}){gpu_str} | Forecast: {predicted_temp}°C ({pred_tag}) | Mode: {target_plan.upper()} | CPU Limit: {target_cpu_limit}% | Action: {action_taken}"
            else:
                console_msg = f"[{time_str}] CPU: {telemetry['cpu_temp']}°C ({src_tag}){gpu_str} | Forecast: {predicted_temp}°C ({pred_tag}) | Load: {telemetry['cpu_util']}% | Gaming: {game_str} | Mode: {target_plan.upper()} | Action: {action_taken}"

            print(console_msg)

            # 7. Asynchronous Model Retraining every 30 loops (60 seconds)
            loop_count += 1
            if loop_count % 30 == 0:
                train_thread = threading.Thread(
                    target=retrain_model_background,
                    args=(predictor,),
                    daemon=True
                )
                train_thread.start()

            # Maintain 2s polling intervals
            elapsed = time.time() - loop_start
            sleep_time = max(0.1, 2.0 - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("Ctrl+C captured. Initiating clean exit...")
    finally:
        cleanup_on_exit()

if __name__ == "__main__":
    main()
