import time
import random
import logging

logger = logging.getLogger("ThermalController.Simulation")

SCENARIOS = {
    "NORMAL_OFFICE": {
        "name": "Normal Office / Idle Load",
        "description": "Simulates light web browsing and background tasks (40–55°C, 15–30% CPU, Idle)",
        "base_temp": 45.0,
        "cpu_util": 20.0,
        "ram_util": 45.0,
        "is_gaming": False,
        "game_name": None
    },
    "GAMING_LOAD": {
        "name": "Standard Gaming Session",
        "description": "Simulates a sustained 1080p/1440p gaming session (75–85°C, 65–80% CPU, Gaming)",
        "base_temp": 78.0,
        "cpu_util": 72.0,
        "ram_util": 68.0,
        "is_gaming": True,
        "game_name": "cyberpunk2077.exe"
    },
    "HEAVY_THERMAL_LOAD": {
        "name": "Heavy Thermal Load",
        "description": "Simulates high-demand gaming/rendering pushing temp into boost reduction zone (90–94°C)",
        "base_temp": 92.0,
        "cpu_util": 88.0,
        "ram_util": 78.0,
        "is_gaming": True,
        "game_name": "cs2.exe"
    },
    "RAPID_SPIKE": {
        "name": "Rapid Temperature Spike",
        "description": "Simulates a sudden thermal jump from 55°C to 96°C to test Proactive ML & Emergency Safety Overrides",
        "base_temp": 96.0,
        "cpu_util": 95.0,
        "ram_util": 82.0,
        "is_gaming": True,
        "game_name": "rdr2.exe"
    },
    "EMERGENCY_CRISIS": {
        "name": "Emergency Thermal Crisis",
        "description": "Simulates a critical sustained 97°C thermal state to verify emergency cooling throttling (85% CPU)",
        "base_temp": 97.5,
        "cpu_util": 98.0,
        "ram_util": 85.0,
        "is_gaming": True,
        "game_name": "eldenring.exe"
    }
}

class SimulationScenarioRunner:
    """
    Provides pre-packaged simulation scenarios for safe interactive demonstrations and unit testing.
    """
    def __init__(self):
        self.active_scenario = None
        self.scenario_start_time = 0.0

    def get_available_scenarios(self) -> dict:
        return SCENARIOS

    def set_scenario(self, scenario_key: str) -> bool:
        if scenario_key in SCENARIOS:
            self.active_scenario = scenario_key
            self.scenario_start_time = time.time()
            logger.info(f"Activated Simulation Scenario: {SCENARIOS[scenario_key]['name']}")
            return True
        elif scenario_key is None or scenario_key == "NONE":
            self.active_scenario = None
            logger.info("Cleared Simulation Scenario.")
            return True
        return False

    def get_telemetry_frame(self) -> dict or None:
        """Returns mock telemetry payload corresponding to active scenario, or None if inactive."""
        if not self.active_scenario or self.active_scenario not in SCENARIOS:
            return None

        spec = SCENARIOS[self.active_scenario]
        
        # Add slight realistic noise
        temp_val = round(spec["base_temp"] + random.uniform(-0.8, 0.8), 1)
        cpu_val = round(max(0, min(100, spec["cpu_util"] + random.uniform(-2.0, 2.0))), 1)
        ram_val = round(max(0, min(100, spec["ram_util"] + random.uniform(-1.0, 1.0))), 1)
        gpu_temp_val = round(max(35.0, temp_val - random.uniform(3.0, 7.0)), 1)
        gpu_util_val = round(min(100.0, cpu_val * (1.1 if spec["is_gaming"] else 0.3)), 1)

        return {
            "timestamp": time.time(),
            "cpu_temp": temp_val,
            "gpu_temp": gpu_temp_val,
            "gpu_util": gpu_util_val,
            "gpu_name": "Simulated NVIDIA GeForce RTX",
            "gpu_source": "SIMULATION",
            "temperature_source": "SIMULATION",
            "temperature_backend": f"Scenario: {spec['name']}",
            "cpu_util": cpu_val,
            "ram_util": ram_val,
            "cpu_freq_mhz": 3200.0 if spec["is_gaming"] else 2200.0,
            "cpu_cores_physical": 8,
            "cpu_cores_logical": 16,
            "is_gaming": spec["is_gaming"],
            "game_name": spec["game_name"]
        }
