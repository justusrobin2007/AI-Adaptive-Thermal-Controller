import os
import json
import logging

logger = logging.getLogger("ThermalController.Config")

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config.json"
)

DEFAULT_CONFIG = {
    "game_list": [
        "cyberpunk2077.exe",
        "cs2.exe",
        "rdr2.exe",
        "valorant.exe",
        "gta5.exe",
        "witcher3.exe",
        "overwatch.exe",
        "leagueoflegends.exe",
        "fortniteclient-win64-shipping.exe",
        "valorant-win64-shipping.exe",
        "eldenring.exe",
        "skyrim.exe"
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
    "hysteresis_seconds": 10,
    "sensor_settings": {
        "prefer_real_sensor": True,
        "force_simulation": False
    },
    "controller_settings": {
        "dry_run": False,
        "enabled": True
    }
}

class SystemConfig:
    """
    Thread-safe configuration manager for thermal thresholds, game process rules,
    sensor preferences, and system settings.
    """
    def __init__(self, config_file: str = CONFIG_PATH):
        self.config_file = config_file
        self.data = self.load_config()

    def load_config(self) -> dict:
        """Loads configuration from config.json or initializes default configuration if missing."""
        if not os.path.exists(self.config_file):
            logger.info("config.json not found. Initializing with default settings.")
            self.save_config(DEFAULT_CONFIG)
            return json.loads(json.dumps(DEFAULT_CONFIG))

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                
            # Merge missing keys from DEFAULT_CONFIG if new attributes were added
            merged = json.loads(json.dumps(DEFAULT_CONFIG))
            for key, val in loaded.items():
                if isinstance(val, dict) and key in merged and isinstance(merged[key], dict):
                    merged[key].update(val)
                else:
                    merged[key] = val
            return merged
        except Exception as e:
            logger.error(f"Error reading config file '{self.config_file}': {e}. Using fallback defaults.")
            return json.loads(json.dumps(DEFAULT_CONFIG))

    def save_config(self, data: dict = None) -> bool:
        """Saves current configuration to disk."""
        if data is not None:
            self.data = data
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            logger.info(f"Successfully saved configuration to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False

    def get_game_list(self) -> list:
        return [g.lower().strip() for g in self.data.get("game_list", [])]

    def add_game(self, game_name: str) -> bool:
        clean_name = game_name.lower().strip()
        if not clean_name:
            return False
        games = self.get_game_list()
        if clean_name not in games:
            games.append(clean_name)
            self.data["game_list"] = games
            return self.save_config()
        return True

    def remove_game(self, game_name: str) -> bool:
        clean_name = game_name.lower().strip()
        games = self.get_game_list()
        if clean_name in games:
            games.remove(clean_name)
            self.data["game_list"] = games
            return self.save_config()
        return False

    def get_thresholds(self) -> dict:
        return self.data.get("thresholds", DEFAULT_CONFIG["thresholds"])

    def set_thresholds(self, thresholds: dict) -> bool:
        self.data["thresholds"].update(thresholds)
        return self.save_config()

    def get_cpu_limits(self) -> dict:
        return self.data.get("cpu_limits", DEFAULT_CONFIG["cpu_limits"])

    def get_hysteresis(self) -> int:
        return int(self.data.get("hysteresis_seconds", 10))

    def set_hysteresis(self, seconds: int) -> bool:
        self.data["hysteresis_seconds"] = max(0, int(seconds))
        return self.save_config()

    def get_sensor_settings(self) -> dict:
        return self.data.get("sensor_settings", DEFAULT_CONFIG["sensor_settings"])

    def set_sensor_settings(self, settings: dict) -> bool:
        self.data["sensor_settings"].update(settings)
        return self.save_config()

    def get_controller_settings(self) -> dict:
        return self.data.get("controller_settings", DEFAULT_CONFIG["controller_settings"])

    def set_controller_settings(self, settings: dict) -> bool:
        self.data["controller_settings"].update(settings)
        return self.save_config()

# Global singleton instance for easy import across modules
sys_config = SystemConfig()
