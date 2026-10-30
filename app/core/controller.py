import sys
import re
import subprocess
import logging
import ctypes
from app.core.config import sys_config

logger = logging.getLogger("ThermalController.Controller")

class ThermalController:
    """
    Manages Windows Power Schemes and Processor Performance limits via powercfg.
    Captures original system power settings at initialization and guarantees clean restoration on exit.
    Includes dry-run fallbacks, admin checks, and unchanged-state skipping for efficiency.
    """

    # Default scheme GUIDs fallback mapping
    GUIDS = {
        "balanced": "381b4222-f694-41f0-9685-ff5bb260df2e",
        "performance": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
        "saver": "a1841308-3541-4fab-bc81-f71556f20b4a"
    }

    def __init__(self, dry_run_override: bool = None):
        self.is_windows = sys.platform == "win32"
        self.has_admin = self._check_admin_rights()
        
        cfg_ctrl = sys_config.get_controller_settings()
        if dry_run_override is not None:
            self.dry_run = dry_run_override
        else:
            self.dry_run = cfg_ctrl.get("dry_run", False) or not self.is_windows or not self.has_admin

        # State tracking
        self.current_plan = "unknown"
        self.current_cpu_max_state = 100
        
        # Original system state capture for restoration
        self.original_plan_guid = None
        self.original_cpu_max_state = 100
        
        if self.is_windows:
            self._capture_original_system_state()

        if not self.is_windows:
            logger.warning("Non-Windows OS detected. ThermalController running in Dry-Run mode.")
        elif not self.has_admin:
            logger.warning("Running without Windows Administrator rights. ThermalController executing in Dry-Run mode.")
        elif self.dry_run:
            logger.info("ThermalController initialized in user-selected DRY-RUN mode.")

    def _check_admin_rights(self) -> bool:
        """Checks if process has Windows Administrator privileges."""
        if not self.is_windows:
            return False
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def _run_command(self, cmd: list) -> tuple:
        """
        Executes a powercfg subprocess command safely with timeouts and error capture.
        
        Returns:
            (success: bool, stdout: str, stderr: str)
        """
        if self.dry_run or not self.is_windows:
            logger.debug(f"[DRY-RUN] Command simulation: {' '.join(cmd)}")
            return True, "DRY_RUN_SUCCESS", ""

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            if result.returncode == 0:
                return True, result.stdout, result.stderr
            else:
                logger.error(f"powercfg command failed ({result.returncode}): {' '.join(cmd)}. Error: {result.stderr.strip()}")
                return False, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"powercfg command timed out: {' '.join(cmd)}")
            return False, "", "Timeout expired"
        except Exception as e:
            logger.error(f"Exception executing powercfg command: {e}")
            return False, "", str(e)

    def _scan_installed_power_schemes(self):
        """Scans installed system power schemes (e.g. Turbo, Performance, Silent, Balanced)."""
        if not self.is_windows:
            return
        try:
            res = subprocess.run(["powercfg", "/list"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout:
                matches = re.findall(r"Power Scheme GUID:\s*([a-fA-F0-9\-]+)\s+\(([^)]+)\)", res.stdout)
                for guid, name in matches:
                    clean_name = name.lower().strip()
                    clean_guid = guid.lower().strip()
                    self.GUIDS[clean_name] = clean_guid
                    if "turbo" in clean_name:
                        self.GUIDS["turbo"] = clean_guid
                        self.GUIDS["performance"] = clean_guid
                    elif "silent" in clean_name or "quiet" in clean_name:
                        self.GUIDS["silent"] = clean_guid
                        self.GUIDS["saver"] = clean_guid
                    elif "performance" in clean_name:
                        self.GUIDS["performance"] = clean_guid
                    elif "balanced" in clean_name:
                        self.GUIDS["balanced"] = clean_guid
                logger.info(f"Discovered system power schemes: {list(self.GUIDS.keys())}")
        except Exception as e:
            logger.warning(f"Unable to scan system power schemes: {e}")

    def _capture_original_system_state(self):
        """Captures the user's current power scheme GUID and CPU max state prior to modifications."""
        self._scan_installed_power_schemes()
        try:
            # 1. Capture active power scheme GUID and name
            success, stdout, _ = self._run_command(["powercfg", "-getactivescheme"])
            if success and stdout and "GUID" in stdout:
                match_guid = re.search(r"GUID:\s*([a-fA-F0-9\-]+)", stdout)
                match_name = re.search(r"\(([^)]+)\)", stdout)
                if match_guid:
                    self.original_plan_guid = match_guid.group(1).lower()
                    logger.info(f"Captured original Windows power plan GUID: {self.original_plan_guid}")
                if match_name:
                    self.current_plan = match_name.group(1).strip()

            # 2. Query maximum processor state for active plan
            success, stdout, _ = self._run_command(["powercfg", "-q", "SCHEME_CURRENT", "SUB_PROCESSOR", "PROCTHROTTLEMAX"])
            if success and stdout:
                # Search for Current AC Power Setting Index (e.g. 0x00000064 -> 100)
                matches = re.findall(r"Current AC Power Setting Index:\s*0x([0-9a-fA-F]+)", stdout)
                if matches:
                    val = int(matches[-1], 16)
                    self.original_cpu_max_state = val
                    self.current_cpu_max_state = val
                    logger.info(f"Captured original Maximum Processor State limit: {val}%")
        except Exception as e:
            logger.warning(f"Unable to query initial power configuration: {e}")

    def get_active_power_plan_name(self) -> str:
        """Queries Windows OS directly for active power scheme name (e.g. Turbo, Performance, Silent, Balanced)."""
        if not self.is_windows:
            return self.current_plan
        try:
            res = subprocess.run(["powercfg", "-getactivescheme"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout:
                match = re.search(r"\(([^)]+)\)", res.stdout)
                if match:
                    return match.group(1).strip()
        except Exception:
            pass
        return self.current_plan

    def set_power_plan(self, plan_name_or_guid: str) -> bool:
        """
        Switches the active Windows power plan.
        Skips execution if requested plan matches the currently active plan.
        """
        plan_clean = plan_name_or_guid.lower().strip()
        
        # Determine target GUID
        target_guid = self.GUIDS.get(plan_clean, plan_clean)
        
        # Unchanged state check
        if self.current_plan == plan_clean or self.current_plan == target_guid:
            logger.debug(f"Power plan unchanged ({plan_clean}). Skipping powercfg command.")
            return True

        logger.info(f"Applying power plan transition: '{self.current_plan}' -> '{plan_clean}' (GUID: {target_guid})")
        cmd = ["powercfg", "-setactive", target_guid]
        success, _, _ = self._run_command(cmd)
        
        if success:
            self.current_plan = plan_clean
            return True
        return False

    def set_cpu_max_state(self, percent: int) -> bool:
        """
        Limits Maximum Processor State (%) on AC and DC power.
        Skips execution if requested CPU state matches current active limit.
        """
        percent = max(50, min(100, int(percent)))
        
        # Unchanged state check
        if self.current_cpu_max_state == percent:
            logger.debug(f"CPU Max State limit unchanged ({percent}%). Skipping powercfg commands.")
            return True

        logger.info(f"Applying Maximum Processor State transition: {self.current_cpu_max_state}% -> {percent}%")
        
        ac_cmd = ["powercfg", "-setacvalueindex", "SCHEME_CURRENT", "SUB_PROCESSOR", "PROCTHROTTLEMAX", str(percent)]
        dc_cmd = ["powercfg", "-setdcvalueindex", "SCHEME_CURRENT", "SUB_PROCESSOR", "PROCTHROTTLEMAX", str(percent)]
        apply_cmd = ["powercfg", "-setactive", "SCHEME_CURRENT"]

        succ_ac, _, _ = self._run_command(ac_cmd)
        succ_dc, _, _ = self._run_command(dc_cmd)
        succ_apply, _, _ = self._run_command(apply_cmd)

        if succ_ac and succ_dc and succ_apply:
            self.current_cpu_max_state = percent
            return True
        return False

    def restore_original_configuration(self) -> bool:
        """Restores user's original Windows power plan GUID and CPU limit captured at startup."""
        logger.info("Restoring original user system power configuration...")
        success_plan = True
        success_limit = True

        if self.original_plan_guid:
            logger.info(f"Restoring original power plan GUID: {self.original_plan_guid}")
            cmd = ["powercfg", "-setactive", self.original_plan_guid]
            succ, _, _ = self._run_command(cmd)
            success_plan = succ
        else:
            # Fallback to balanced if original GUID was unavailable
            success_plan = self.set_power_plan("balanced")

        if self.original_cpu_max_state:
            logger.info(f"Restoring original CPU Maximum State: {self.original_cpu_max_state}%")
            success_limit = self.set_cpu_max_state(self.original_cpu_max_state)

        return success_plan and success_limit

    def set_dry_run(self, status: bool):
        """Toggles dry run mode dynamically."""
        self.dry_run = status
        logger.info(f"ThermalController dry-run mode set to: {status}")

    def get_status(self) -> dict:
        """Returns comprehensive status dictionary."""
        active_name = self.get_active_power_plan_name()
        return {
            "power_plan": self.current_plan,
            "active_os_power_plan": active_name,
            "max_cpu_percent": self.current_cpu_max_state,
            "original_plan_guid": self.original_plan_guid,
            "original_cpu_max_state": self.original_cpu_max_state,
            "admin_privileges": self.has_admin,
            "platform_windows": self.is_windows,
            "dry_run": self.dry_run
        }
