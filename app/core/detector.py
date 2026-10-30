import logging
from app.core.config import sys_config

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger("ThermalController.Detector")

class GameDetector:
    """
    Monitors running system processes against a configurable list of gaming executables.
    Integrates with app.core.config for dynamic persistence and manual testing controls.
    """
    def __init__(self, custom_games: list = None):
        self.mock_gaming_active = False
        self.mock_game_name = "cyberpunk2077.exe"
        
        # Load configurable game list from sys_config
        self.target_games = set(sys_config.get_game_list())
        
        if custom_games:
            for g in custom_games:
                clean = g.lower().strip()
                if clean:
                    self.target_games.add(clean)

    def reload_game_list(self):
        """Reloads game list from configuration manager."""
        self.target_games = set(sys_config.get_game_list())

    def check_is_gaming(self) -> tuple:
        """
        Scans running system processes for target gaming executables.
        
        Returns:
            (is_gaming: bool, detected_game_name: str or None)
        """
        if self.mock_gaming_active:
            return True, self.mock_game_name

        if not psutil:
            logger.warning("psutil is not installed. Unable to execute process scan.")
            return False, None

        # Reload configuration in case dashboard or config added new games
        self.target_games = set(sys_config.get_game_list())

        try:
            # Optimized psutil scan requesting only process names
            for proc in psutil.process_iter(attrs=['name']):
                try:
                    proc_name = proc.info.get('name')
                    if proc_name:
                        name_lower = proc_name.lower().strip()
                        # 1. Exact match
                        if name_lower in self.target_games:
                            logger.info(f"Monitored game process detected: {proc_name}")
                            return True, proc_name
                        
                        # 2. Stem match (e.g. gta5 matching GTA5_Enhanced_BE.exe)
                        for target in self.target_games:
                            stem = target.replace(".exe", "").strip()
                            if len(stem) >= 4 and stem in name_lower:
                                logger.info(f"Monitored game process variant detected ({proc_name} matched stem '{stem}')")
                                return True, proc_name
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            logger.error(f"Error during system process scanning: {e}")

        return False, None

    def get_formatted_status(self) -> str:
        """Returns a clean display string representing current gaming status."""
        is_gaming, game_name = self.check_is_gaming()
        if is_gaming:
            return f"GAMING: YES — {game_name}"
        return "GAMING: NO"

    def add_target_game(self, process_name: str) -> bool:
        """Dynamically registers a new game executable name and persists to config.json."""
        clean_name = process_name.lower().strip()
        if clean_name:
            self.target_games.add(clean_name)
            success = sys_config.add_game(clean_name)
            if success:
                logger.info(f"Registered and saved new game process: {clean_name}")
            return success
        return False

    def remove_target_game(self, process_name: str) -> bool:
        """Deregisters a game executable name and persists change to config.json."""
        clean_name = process_name.lower().strip()
        if clean_name in self.target_games:
            self.target_games.remove(clean_name)
        success = sys_config.remove_game(clean_name)
        if success:
            logger.info(f"Deregistered game process: {clean_name}")
        return success

    def set_mock_gaming(self, status: bool, mock_name: str = "cyberpunk2077.exe"):
        """Toggles manual gaming simulation mode for testing."""
        self.mock_gaming_active = status
        self.mock_game_name = mock_name
        logger.info(f"Mock gaming state changed -> Active: {status}, Executable: {mock_name}")
