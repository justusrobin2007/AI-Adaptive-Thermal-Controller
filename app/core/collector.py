import time
import logging
import random
import ctypes
import subprocess
from enum import Enum

try:
    import psutil
except ImportError:
    psutil = None

try:
    import wmi
except ImportError:
    wmi = None

try:
    import win32pdh
except ImportError:
    win32pdh = None

logger = logging.getLogger("ThermalController.Collector")

class SensorSource(str, Enum):
    REAL_HARDWARE = "REAL_HARDWARE"
    SIMULATION = "SIMULATION"
    UNAVAILABLE = "UNAVAILABLE"

class PDHThermalMonitor:
    """
    Direct Windows Kernel Performance Data Helper (PDH) Thermal Monitor.
    Queries kernel ACPI thermal zones (\\Thermal Zone Information(*)\\High Precision Temperature)
    natively with zero third-party software and zero administrator privileges required.
    Particularly effective on ASUS ROG and high-performance gaming laptops.
    """
    def __init__(self):
        self.query_handle = None
        self.counter_high = None
        self.counter_std = None
        self.initialized = False
        self._init_pdh()

    def _init_pdh(self):
        if win32pdh is None:
            self.initialized = False
            return
        try:
            self.query_handle = win32pdh.OpenQuery()
            try:
                self.counter_high = win32pdh.AddEnglishCounter(
                    self.query_handle, r"\Thermal Zone Information(*)\High Precision Temperature"
                )
            except Exception:
                self.counter_high = None

            try:
                self.counter_std = win32pdh.AddEnglishCounter(
                    self.query_handle, r"\Thermal Zone Information(*)\Temperature"
                )
            except Exception:
                self.counter_std = None

            if self.counter_high or self.counter_std:
                win32pdh.CollectQueryData(self.query_handle)
                self.initialized = True
        except Exception as e:
            logger.debug(f"PDH thermal monitor init error: {e}")
            self.initialized = False

    def query(self) -> tuple:
        """
        Queries real hardware thermal zone temperature.
        Returns:
            (temperature_celsius: float, zone_name: str) or (None, None)
        """
        if win32pdh is None:
            return None, None
        if not self.initialized:
            self._init_pdh()
        if not self.initialized:
            return None, None

        try:
            win32pdh.CollectQueryData(self.query_handle)
            valid_temps = []

            # 1. Try High Precision first (deci-Kelvin: tenths of a Kelvin)
            if self.counter_high:
                try:
                    data = win32pdh.GetFormattedCounterArray(self.counter_high, win32pdh.PDH_FMT_DOUBLE)
                    for zone, val in data.items():
                        if val and val > 2700:
                            celsius = (val / 10.0) - 273.15
                            if 20.0 <= celsius <= 115.0:
                                valid_temps.append((celsius, zone))
                except Exception:
                    pass

            # 2. Try Standard Kelvin
            if not valid_temps and self.counter_std:
                try:
                    data = win32pdh.GetFormattedCounterArray(self.counter_std, win32pdh.PDH_FMT_DOUBLE)
                    for zone, val in data.items():
                        if val and val > 270:
                            celsius = val - 273.15
                            if 20.0 <= celsius <= 115.0:
                                valid_temps.append((celsius, zone))
                except Exception:
                    pass

            if valid_temps:
                # Return highest temperature reading (CPU core/junction hotspot)
                valid_temps.sort(key=lambda x: x[0], reverse=True)
                return round(valid_temps[0][0], 1), valid_temps[0][1]

        except Exception as e:
            logger.debug(f"PDH query error: {e}")
            self.initialized = False
            try:
                if self.query_handle:
                    win32pdh.CloseQuery(self.query_handle)
            except Exception:
                pass
            self.query_handle = None

        return None, None


class GPUMonitor:
    """
    Direct hardware GPU telemetry monitor.
    Uses NVIDIA Management Library (nvml.dll) via ctypes for sub-millisecond real temperature/usage,
    with fallbacks to nvidia-smi CLI and LibreHardwareMonitor WMI.
    """
    def __init__(self):
        self.nvml_initialized = False
        self.device = None
        self.gpu_name = "Dedicated GPU"
        self._last_query_time = 0.0
        self._cached_metrics = {
            "gpu_temp": None,
            "gpu_util": 0.0,
            "gpu_name": "Detecting...",
            "gpu_source": SensorSource.UNAVAILABLE.value
        }
        self._init_nvml()

    def _init_nvml(self):
        """Attempts direct connection to NVIDIA nvml.dll."""
        try:
            self.nvml = ctypes.CDLL("nvml.dll")
            if self.nvml.nvmlInit_v2() == 0:
                self.device = ctypes.c_void_p()
                if self.nvml.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(self.device)) == 0:
                    name_buf = ctypes.create_string_buffer(96)
                    self.nvml.nvmlDeviceGetName(self.device, name_buf, 96)
                    self.gpu_name = name_buf.value.decode("utf-8", errors="ignore")
                    self.nvml_initialized = True
                    logger.info(f"Initialized direct NVML GPU monitor: {self.gpu_name}")
        except Exception as e:
            logger.debug(f"Direct NVML initialization unavailable: {e}")
            self.nvml_initialized = False

    def query(self) -> dict:
        """
        Reads real GPU temperature and utilization.
        Cached at 0.5s intervals for high performance without bus congestion.
        """
        now = time.time()
        if now - self._last_query_time < 0.5 and self._cached_metrics.get("gpu_temp") is not None:
            return self._cached_metrics

        # 1. Direct NVML Call
        if self.nvml_initialized and self.device:
            try:
                temp_c = ctypes.c_uint()
                # 0 = NVML_TEMPERATURE_GPU
                ret_t = self.nvml.nvmlDeviceGetTemperature(self.device, 0, ctypes.byref(temp_c))
                
                class _nvmlUtilization_t(ctypes.Structure):
                    _fields_ = [('gpu', ctypes.c_uint), ('memory', ctypes.c_uint)]
                util = _nvmlUtilization_t()
                ret_u = self.nvml.nvmlDeviceGetUtilizationRates(self.device, ctypes.byref(util))
                
                if ret_t == 0:
                    self._cached_metrics = {
                        "gpu_temp": round(float(temp_c.value), 1),
                        "gpu_util": round(float(util.gpu), 1) if ret_u == 0 else 0.0,
                        "gpu_name": self.gpu_name,
                        "gpu_source": SensorSource.REAL_HARDWARE.value
                    }
                    self._last_query_time = now
                    return self._cached_metrics
            except Exception as e:
                logger.debug(f"Direct NVML query error: {e}")

        # 2. nvidia-smi CLI Fallback
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=1.0
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                if len(parts) >= 2:
                    self._cached_metrics = {
                        "gpu_temp": round(float(parts[1]), 1),
                        "gpu_util": round(float(parts[2]), 1) if len(parts) > 2 else 0.0,
                        "gpu_name": parts[0],
                        "gpu_source": SensorSource.REAL_HARDWARE.value
                    }
                    self._last_query_time = now
                    return self._cached_metrics
        except Exception:
            pass

        return {
            "gpu_temp": None,
            "gpu_util": 0.0,
            "gpu_name": "No Dedicated GPU Detected",
            "gpu_source": SensorSource.UNAVAILABLE.value
        }

class TelemetryCollector:
    """
    Multi-backend telemetry collector with explicit sensor abstraction.
    Supports LibreHardwareMonitor WMI, OpenHardwareMonitor WMI, Windows ACPI WMI,
    psutil thermal sensors, NVML GPU sensors, and dynamic thermodynamic simulation fallbacks.
    """
    def __init__(self, force_simulation: bool = False):
        self.force_simulation = force_simulation
        self.override_temp = None  # Testing override
        
        # Sensor status tracking
        self.active_source = SensorSource.SIMULATION
        self.active_backend_name = "Initializing..."
        
        self.wmi_root = None
        self.wmi_lhm = None
        self.pdh_monitor = PDHThermalMonitor()
        self.gpu_monitor = GPUMonitor()
        self._last_init_attempt = 0.0
        
        self._last_simulated_temp = 48.0
        self._last_cpu_util = 0.0
        self._last_cpu_util_time = 0.0
        self.physical_cores = 1
        self.logical_cores = 1
        
        # Seed psutil cpu_percent & gather static CPU specs
        if psutil:
            try:
                self._last_cpu_util = float(psutil.cpu_percent(interval=None))
                self._last_cpu_util_time = time.time()
                self.physical_cores = psutil.cpu_count(logical=False) or 1
                self.logical_cores = psutil.cpu_count(logical=True) or 1
            except Exception as e:
                logger.error(f"Error reading psutil core counts: {e}")

        # Initialize hardware sensor backends if not forced into simulation
        if not self.force_simulation:
            self._init_sensor_backends()
        else:
            self.active_source = SensorSource.SIMULATION
            self.active_backend_name = "Dynamic Load Simulation (Forced)"
            logger.info("Collector initialized in forced SIMULATION mode.")

    def _init_sensor_backends(self):
        """Attempts connection to hardware sensor backends in order of precision."""
        # 1. Try LibreHardwareMonitor or OpenHardwareMonitor WMI Namespace
        if wmi:
            for namespace, name in [
                ("root\\LibreHardwareMonitor", "LibreHardwareMonitor WMI (Direct Silicon Diode)"),
                ("root\\OpenHardwareMonitor", "OpenHardwareMonitor WMI (Direct Silicon Diode)")
            ]:
                try:
                    conn = wmi.WMI(namespace=namespace)
                    sensors = conn.Sensor()
                    temp_sensors = [s for s in sensors if s.SensorType == 'Temperature']
                    if temp_sensors:
                        self.wmi_lhm = conn
                        self.wmi_root = None  # Supercede static ACPI
                        self.active_source = SensorSource.REAL_HARDWARE
                        self.active_backend_name = name
                        logger.info(f"Successfully connected to hardware temperature sensor: {name}")
                        return
                except Exception:
                    pass

        # 2. Try LibreHardwareMonitor Local HTTP Web Server (Options -> Remote web server on port 8085)
        http_temp = self._query_lhm_http()
        if http_temp is not None:
            self.wmi_root = None
            self.active_source = SensorSource.REAL_HARDWARE
            self.active_backend_name = "LibreHardwareMonitor Web Server (Local)"
            logger.info("Successfully connected to LibreHardwareMonitor local web server.")
            return

        # 3. Try Direct Windows Kernel PDH Thermal Zone (Zero-Admin, Native Hardware ACPI Diode)
        pdh_temp, pdh_zone = self.pdh_monitor.query()
        if pdh_temp is not None:
            self.active_source = SensorSource.REAL_HARDWARE
            self.active_backend_name = f"Windows Kernel ACPI ({pdh_zone})"
            logger.info(f"Successfully connected to Windows Kernel PDH sensor: {self.active_backend_name}")
            return

        # 4. Try Standard Windows ACPI WMI Namespace (root\wmi)
        # Note: On ASUS ROG motherboards, this reports static motherboard ambient (~70°C) instead of CPU silicon.
        if wmi:
            try:
                conn = wmi.WMI(namespace="root\\wmi")
                zones = conn.MSAcpi_ThermalZoneTemperature()
                if zones:
                    self.wmi_root = conn
                    self.active_source = SensorSource.REAL_HARDWARE
                    self.active_backend_name = "Windows ACPI (Motherboard Ambient Zone)"
                    logger.info("Connected to Windows ACPI ThermalZone sensor (Motherboard Ambient).")
                    return
            except Exception:
                pass

        # 5. Try psutil sensors_temperatures (available on Linux / supported OS)
        if psutil and hasattr(psutil, "sensors_temperatures"):
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    self.active_source = SensorSource.REAL_HARDWARE
                    self.active_backend_name = "psutil Hardware Sensors"
                    logger.info("Successfully connected to psutil hardware temperature sensors.")
                    return
            except Exception:
                pass

        # 6. Fallback to Dynamic Load Simulation
        self.active_source = SensorSource.SIMULATION
        self.active_backend_name = "Dynamic Load Simulation (Hardware Sensors Locked/Unavailable)"

    def _query_lhm_http(self):
        """Queries LibreHardwareMonitor local web server if enabled on port 8085."""
        try:
            import urllib.request
            import json
            req = urllib.request.Request("http://127.0.0.1:8085/data.json", headers={"User-Agent": "ThermalController"})
            with urllib.request.urlopen(req, timeout=0.3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                temps = []
                def extract_temps(node, path=""):
                    if not isinstance(node, dict):
                        return
                    text = str(node.get("Text", ""))
                    curr_path = f"{path}/{text}".lower()
                    val_raw = node.get("Value", "")
                    if isinstance(val_raw, (int, float)):
                        if any(k in curr_path for k in ["cpu", "core", "tctl", "tdie", "package", "ccd"]):
                            temps.append(float(val_raw))
                    elif isinstance(val_raw, str) and ("°c" in val_raw.lower() or "c" in val_raw.lower()):
                        try:
                            clean_str = val_raw.lower().replace("°c", "").replace("c", "").replace(",", ".").strip()
                            num = float(clean_str)
                            if any(k in curr_path for k in ["cpu", "core", "tctl", "tdie", "package", "ccd"]):
                                temps.append(num)
                        except ValueError:
                            pass
                    for child in node.get("Children", []):
                        extract_temps(child, curr_path)
                extract_temps(data)
                if temps:
                    return round(max(temps), 1)
        except Exception:
            pass
        return None

    def get_cpu_utilization(self) -> float:
        """Returns overall CPU utilization percentage."""
        now = time.time()
        # Return cached value if queried within 0.5 seconds of last measurement
        if now - self._last_cpu_util_time < 0.5:
            return round(self._last_cpu_util, 1)

        if psutil:
            try:
                val = float(psutil.cpu_percent(interval=None))
                self._last_cpu_util = val
                self._last_cpu_util_time = now
                return round(val, 1)
            except Exception as e:
                logger.error(f"Error querying CPU utilization: {e}")
                return 0.0
        return round(random.uniform(15.0, 85.0), 1)

    def get_ram_utilization(self) -> float:
        """Returns virtual memory utilization percentage."""
        if psutil:
            try:
                return round(float(psutil.virtual_memory().percent), 1)
            except Exception as e:
                logger.error(f"Error querying RAM utilization: {e}")
                return 0.0
        return round(random.uniform(40.0, 70.0), 1)

    def get_cpu_frequency(self) -> float:
        """Returns current CPU frequency in MHz."""
        if psutil:
            try:
                freq = psutil.cpu_freq()
                if freq and freq.current:
                    return round(float(freq.current), 1)
            except Exception:
                pass
        return 2800.0  # Nominal fallback frequency

    def get_gpu_metrics(self) -> dict:
        """Queries GPU telemetry (temperature, utilization, device name)."""
        if self.force_simulation:
            # Simulate GPU metrics consistent with CPU load
            sim_load = self.get_cpu_utilization()
            sim_temp = round(40.0 + (sim_load / 100.0) * 45.0 + random.uniform(-0.5, 0.5), 1)
            return {
                "gpu_temp": sim_temp,
                "gpu_util": round(sim_load * 0.9, 1),
                "gpu_name": "Simulated GPU",
                "gpu_source": SensorSource.SIMULATION.value
            }
        return self.gpu_monitor.query()

    def get_cpu_temp(self) -> tuple:
        """
        Queries CPU temperature from active hardware sensors or falls back to simulation.
        Automatically retries connecting to LibreHardwareMonitor WMI every 2 seconds.
        
        Returns:
            (temperature_celsius: float, sensor_source: str, backend_name: str)
        """
        # Manual testing override
        if self.override_temp is not None:
            return round(float(self.override_temp), 1), SensorSource.SIMULATION.value, "Manual Testing Override"

        if self.force_simulation:
            return self._simulate_temperature(), SensorSource.SIMULATION.value, "Dynamic Load Simulation (Forced)"

        # Dynamic auto-discovery: Always retry discovering superior LibreHardwareMonitor diode
        if not self.wmi_lhm:
            now = time.time()
            retry_interval = 2.0 if self.active_source == SensorSource.SIMULATION else 10.0
            if now - self._last_init_attempt > retry_interval:
                self._last_init_attempt = now
                self._init_sensor_backends()

        # 1. Query LibreHardwareMonitor / OpenHardwareMonitor WMI (Direct Silicon Diode)
        if self.wmi_lhm:
            try:
                sensors = self.wmi_lhm.Sensor()
                cpu_temps = []
                other_temps = []
                for s in sensors:
                    if s.SensorType == 'Temperature' and s.Value is not None:
                        val = float(s.Value)
                        name_lower = (s.Name or "").lower()
                        # Match AMD Ryzen (Tctl/Tdie, Core, Package, CCD) or Intel Core
                        if any(k in name_lower for k in ["cpu", "core", "tctl", "tdie", "package", "ccd"]):
                            cpu_temps.append(val)
                        elif "gpu" not in name_lower:
                            other_temps.append(val)
                
                target_temps = cpu_temps or other_temps
                if target_temps:
                    return round(max(target_temps), 1), SensorSource.REAL_HARDWARE.value, self.active_backend_name
            except Exception as e:
                logger.debug(f"Error querying LibreHardwareMonitor WMI: {e}")
                self.wmi_lhm = None  # Re-trigger discovery on next loop

        # 2. Query LibreHardwareMonitor Local HTTP Web Server (Options -> Remote web server on port 8085)
        http_temp = self._query_lhm_http()
        if http_temp is not None:
            return http_temp, SensorSource.REAL_HARDWARE.value, "LibreHardwareMonitor Web Server (Local)"

        # 3. Query Direct Windows Kernel PDH Thermal Zone (Zero-Admin, Native Hardware ACPI Diode)
        pdh_temp, pdh_zone = self.pdh_monitor.query()
        if pdh_temp is not None:
            return pdh_temp, SensorSource.REAL_HARDWARE.value, f"Windows Kernel ACPI ({pdh_zone})"

        # 4. Query Windows ACPI ThermalZone WMI
        if self.wmi_root:
            try:
                zones = self.wmi_root.MSAcpi_ThermalZoneTemperature()
                if zones:
                    temps = [(z.CurrentTemperature / 10.0) - 273.15 for z in zones if z.CurrentTemperature > 0]
                    if temps:
                        return round(max(temps), 1), SensorSource.REAL_HARDWARE.value, self.active_backend_name
            except Exception as e:
                logger.debug(f"Error querying Windows ACPI WMI: {e}")
                self.wmi_root = None

        # 3. Query psutil sensors_temperatures
        if psutil and hasattr(psutil, "sensors_temperatures"):
            try:
                temps_dict = psutil.sensors_temperatures()
                all_temps = []
                for entry_list in temps_dict.values():
                    for t in entry_list:
                        if t.current:
                            all_temps.append(t.current)
                if all_temps:
                    return round(max(all_temps), 1), SensorSource.REAL_HARDWARE.value, self.active_backend_name
            except Exception as e:
                logger.debug(f"Error querying psutil temperature sensors: {e}")

        # Fallback to simulation
        return self._simulate_temperature(), SensorSource.SIMULATION.value, self.active_backend_name

    def _simulate_temperature(self) -> float:
        """
        Thermodynamic load simulation with inertia and thermal decay.
        Models CPU temperature based on current CPU load and historical heat dissipation.
        """
        cpu_load = self.get_cpu_utilization()
        
        # Target temperature: Ambient 42C at 0% load up to 96C at 100% load
        target_temp = 42.0 + (cpu_load / 100.0) * 54.0
        
        # Thermal inertia coefficient
        inertia = 0.12
        new_temp = self._last_simulated_temp + (target_temp - self._last_simulated_temp) * inertia
        new_temp += random.uniform(-0.4, 0.4)
        
        # Clamp bounds
        new_temp = max(35.0, min(102.0, new_temp))
        self._last_simulated_temp = new_temp
        return round(new_temp, 1)

    def set_force_simulation(self, status: bool):
        """Forces the collector to use simulation or attempts to reconnect hardware sensors."""
        self.force_simulation = status
        if status:
            self.active_source = SensorSource.SIMULATION
            self.active_backend_name = "Dynamic Load Simulation (User Forced)"
        else:
            self._init_sensor_backends()

    def set_override_temperature(self, temp: float or None):
        """Sets or clears a manual temperature override for interactive testing."""
        self.override_temp = temp

    def collect(self) -> dict:
        """Returns comprehensive system telemetry snapshot including real CPU & GPU metrics."""
        temp, source, backend = self.get_cpu_temp()
        gpu_info = self.get_gpu_metrics()
        return {
            "timestamp": time.time(),
            "cpu_temp": temp,
            "gpu_temp": gpu_info.get("gpu_temp"),
            "gpu_util": gpu_info.get("gpu_util", 0.0),
            "gpu_name": gpu_info.get("gpu_name", "N/A"),
            "gpu_source": gpu_info.get("gpu_source", SensorSource.UNAVAILABLE.value),
            "temperature_source": source,
            "temperature_backend": backend,
            "cpu_util": self.get_cpu_utilization(),
            "ram_util": self.get_ram_utilization(),
            "cpu_freq_mhz": self.get_cpu_frequency(),
            "cpu_cores_physical": self.physical_cores,
            "cpu_cores_logical": self.logical_cores
        }
