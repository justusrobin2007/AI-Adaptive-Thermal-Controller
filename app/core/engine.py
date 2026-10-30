import logging
from app.core.config import sys_config

logger = logging.getLogger("ThermalController.Engine")

class DecisionEngine:
    """
    Hybrid Thermal Control Decision Engine.
    Combines Proactive ML Forecasting with Immutable Actual Temperature Safety Overrides
    and Configurable Hysteresis Transition Smoothing.
    """
    def __init__(self, hysteresis_seconds: int = None):
        self.active_plan = None
        self.active_cpu_limit = None
        self.last_transition_time = 0.0
        
        # Override hysteresis duration if passed, else load from config
        self.custom_hysteresis = hysteresis_seconds

    def _get_config_values(self) -> tuple:
        """Loads live threshold, CPU limit, and hysteresis parameters from sys_config."""
        thresholds = sys_config.get_thresholds()
        limits = sys_config.get_cpu_limits()
        hysteresis = self.custom_hysteresis if self.custom_hysteresis is not None else sys_config.get_hysteresis()
        return thresholds, limits, hysteresis

    def evaluate(self, telemetry: dict, predicted_temp: float, is_gaming: bool, current_time: float) -> dict:
        """
        Evaluates current metrics and predicted temperature against safety and performance rules.
        
        Args:
            telemetry (dict): Current state telemetry containing 'cpu_temp'.
            predicted_temp (float): Predicted temperature 10s in future.
            is_gaming (bool): True if gaming process is detected.
            current_time (float): Epoch timestamp.
            
        Returns:
            dict containing decision mode, cpu_limit, reason, emergency_override, hysteresis_blocked.
        """
        thresholds, limits, hysteresis_sec = self._get_config_values()
        
        cool_t = thresholds.get("cool_threshold", 80.0)
        balanced_t = thresholds.get("balanced_threshold", 90.0)
        boost_red_t = thresholds.get("boost_reduction_threshold", 95.0)
        emergency_t = thresholds.get("emergency_threshold", 95.0)
        
        norm_limit = limits.get("normal_cpu_limit", 100)
        boost_red_limit = limits.get("boost_reduced_cpu_limit", 99)
        emerg_limit = limits.get("emergency_cpu_limit", 85)

        current_temp = float(telemetry.get("cpu_temp", 50.0))
        emergency_override = False
        hysteresis_blocked = False

        # ---------------------------------------------------------
        # Step 1: Proactive Layer (Evaluated on Predicted Temp)
        # ---------------------------------------------------------
        if predicted_temp < cool_t:
            target_plan = "performance" if is_gaming else "balanced"
            target_cpu_limit = norm_limit
            reason = f"Proactive Forecast ({predicted_temp}°C < {cool_t}°C): {target_plan.upper()} / {norm_limit}% CPU"

        elif cool_t <= predicted_temp < balanced_t:
            target_plan = "balanced"
            target_cpu_limit = norm_limit
            reason = f"Proactive Forecast ({predicted_temp}°C): BALANCED / {norm_limit}% CPU"

        elif balanced_t <= predicted_temp < boost_red_t:
            target_plan = "balanced"
            target_cpu_limit = boost_red_limit
            reason = f"Proactive Forecast ({predicted_temp}°C >= {balanced_t}°C): Boost reduction / {boost_red_limit}% CPU"

        else: # predicted_temp >= emergency_t
            target_plan = "saver"
            target_cpu_limit = emerg_limit
            reason = f"Proactive Forecast ({predicted_temp}°C >= {emergency_t}°C): Aggressive cooling / {emerg_limit}% CPU"

        # ---------------------------------------------------------
        # Step 2: Safety Override Layer (Evaluated on Actual Current Temp)
        # ---------------------------------------------------------
        if current_temp >= emergency_t and target_cpu_limit > emerg_limit:
            target_plan = "saver"
            target_cpu_limit = emerg_limit
            emergency_override = True
            reason = f"EMERGENCY OVERRIDE: Actual Temp ({current_temp}°C >= {emergency_t}°C) -> SAVER / {emerg_limit}% CPU"

        elif current_temp >= balanced_t and target_cpu_limit > boost_red_limit:
            target_plan = "balanced"
            target_cpu_limit = boost_red_limit
            emergency_override = True
            reason = f"SAFETY OVERRIDE: Actual Temp ({current_temp}°C >= {balanced_t}°C) -> BALANCED / {boost_red_limit}% CPU"

        # ---------------------------------------------------------
        # Step 3: Hysteresis Smoothing Layer
        # ---------------------------------------------------------
        change_needed = (target_plan != self.active_plan) or (target_cpu_limit != self.active_cpu_limit)

        if change_needed:
            time_since_last = current_time - self.last_transition_time
            # Emergency thermal interventions bypass hysteresis for hardware protection
            is_emergency_switch = emergency_override or (target_cpu_limit < norm_limit and (self.active_cpu_limit is None or target_cpu_limit < self.active_cpu_limit))

            if is_emergency_switch or time_since_last >= hysteresis_sec or self.active_plan is None:
                self.active_plan = target_plan
                self.active_cpu_limit = target_cpu_limit
                self.last_transition_time = current_time
                status_reason = f"{reason} [APPLIED]"
            else:
                # Transition blocked by hysteresis
                hysteresis_blocked = True
                target_plan = self.active_plan
                target_cpu_limit = self.active_cpu_limit
                status_reason = f"Transition blocked by hysteresis ({time_since_last:.1f}s / {hysteresis_sec}s required)"
                logger.info(status_reason)
        else:
            status_reason = f"{reason} [NO CHANGE]"

        return {
            "mode": target_plan,
            "cpu_limit": target_cpu_limit,
            "reason": status_reason,
            "predicted_temp": round(float(predicted_temp), 1),
            "current_temp": round(float(current_temp), 1),
            "emergency_override": emergency_override,
            "hysteresis_blocked": hysteresis_blocked
        }
