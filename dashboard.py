import os
import sys
import re
import time
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

# Ensure App packages can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import sys_config
from app.core.simulation import SCENARIOS

# Page Configuration
st.set_page_config(
    page_title="Thermal Controller",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Paths
CSV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CSV_PATH = os.path.join(CSV_DIR, "thermal_log.csv")

# Apple Design System & Frosted Glassmorphism
st.markdown("""
    <style>
    /* -------------------------------------------------------------
       1. Apple Typography & Global Canvas
       ------------------------------------------------------------- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"], [class*="st-"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", "Inter", sans-serif !important;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }
    
    .tabular-nums, .metric-val, code, pre {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", "Inter", sans-serif !important;
        font-variant-numeric: tabular-nums;
        -webkit-font-feature-settings: "tnum";
        font-feature-settings: "tnum";
    }

    /* -------------------------------------------------------------
       2. Hide Default Streamlit Chrome / Clutter
       ------------------------------------------------------------- */
    #MainMenu { visibility: hidden !important; display: none !important; }
    header { visibility: hidden !important; display: none !important; }
    footer { visibility: hidden !important; display: none !important; }
    [data-testid="stToolbar"] { visibility: hidden !important; display: none !important; }
    [data-testid="stDecoration"] { visibility: hidden !important; display: none !important; }
    [data-testid="stStatusWidget"] { visibility: hidden !important; display: none !important; }
    .stDeployButton { display: none !important; }
    button[title="View fullscreen"] { visibility: hidden !important; }
    [data-testid="stToast"] { display: none !important; }
    
    /* -------------------------------------------------------------
       3. Main Dark Glass Canvas (macOS Space Gray Aesthetic)
       ------------------------------------------------------------- */
    .stApp {
        background-color: #0b0c0e !important;
        background-image: 
            radial-gradient(ellipse 90% 40% at 50% -15%, rgba(120, 130, 160, 0.12), transparent 70%),
            radial-gradient(ellipse 60% 30% at 90% 100%, rgba(60, 70, 95, 0.08), transparent 70%) !important;
        color: #f5f5f7 !important;
    }

    div.block-container {
        padding-top: 1.4rem !important;
        padding-bottom: 2.5rem !important;
        max-width: 96% !important;
    }

    /* Minimalist Apple Scrollbar */
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.16); border-radius: 9999px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.28); }

    /* -------------------------------------------------------------
       4. Apple macOS Settings Inspector (Sidebar)
       ------------------------------------------------------------- */
    [data-testid="stSidebar"] {
        background: rgba(18, 19, 25, 0.88) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
        backdrop-filter: blur(40px) saturate(180%);
        -webkit-backdrop-filter: blur(40px) saturate(180%);
    }

    /* Force all text in sidebar to be crisp, readable, high-contrast white */
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] label p,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] div[data-testid="stWidgetLabel"] label,
    [data-testid="stSidebar"] div[data-testid="stWidgetLabel"] p,
    [data-testid="stSidebar"] div[data-testid="stWidgetLabel"] span {
        color: #f5f5f7 !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        letter-spacing: -0.01em !important;
    }

    /* Section Headings */
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] h4 {
        color: rgba(235, 235, 245, 0.5) !important;
        font-size: 0.72rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        margin-top: 1.3rem !important;
        margin-bottom: 0.5rem !important;
    }

    /* Apple Switch Toggles */
    div[data-testid="stToggle"] {
        padding: 4px 0 !important;
        margin-bottom: 6px !important;
    }
    div[data-testid="stToggle"] label {
        cursor: pointer !important;
    }
    div[data-testid="stToggle"] label p {
        color: #f5f5f7 !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
    }
    /* Switch checked: Apple Green */
    div[data-testid="stToggle"] [aria-checked="true"] {
        background-color: #30d158 !important;
    }
    /* Switch unchecked: Translucent Gray */
    div[data-testid="stToggle"] [aria-checked="false"] {
        background-color: rgba(120, 120, 128, 0.35) !important;
    }
    /* Switch thumb knob */
    div[data-testid="stToggle"] [aria-checked] > div {
        background-color: #ffffff !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.35) !important;
    }

    /* Apple Sliders (BaseWeb Slider Components) */
    div[data-baseweb="slider"] {
        margin-top: 6px !important;
        margin-bottom: 16px !important;
    }
    /* Slider Track Background */
    div[data-baseweb="slider"] > div > div {
        background: rgba(255, 255, 255, 0.12) !important;
        height: 4px !important;
        border-radius: 9999px !important;
    }
    /* Slider Active Fill (Apple Blue) */
    div[data-baseweb="slider"] > div > div > div {
        background: #0071e3 !important;
        height: 4px !important;
        border-radius: 9999px !important;
    }
    /* Slider Thumb (Knob) */
    div[data-baseweb="slider"] [role="slider"] {
        background: #ffffff !important;
        border: 0.5px solid rgba(0, 0, 0, 0.06) !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4) !important;
        width: 15px !important;
        height: 15px !important;
        border-radius: 50% !important;
    }
    /* Floating Thumb Value Pill */
    div[data-testid="stThumbValue"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif !important;
        font-size: 0.72rem !important;
        font-weight: 600 !important;
        color: #ffffff !important;
        background: rgba(30, 32, 40, 0.95) !important;
        border: 1px solid rgba(255, 255, 255, 0.18) !important;
        border-radius: 6px !important;
        padding: 2px 6px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4) !important;
    }
    /* Min/Max ticks below slider */
    div[data-testid="stSliderTickBarMin"],
    div[data-testid="stSliderTickBarMax"] {
        color: rgba(235, 235, 245, 0.35) !important;
        font-size: 0.68rem !important;
    }

    /* Text Inputs & Form Controls */
    [data-testid="stSidebar"] input[type="text"],
    [data-testid="stSidebar"] input[type="number"] {
        background: rgba(255, 255, 255, 0.06) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 8px !important;
        color: #f5f5f7 !important;
        font-size: 0.82rem !important;
        padding: 6px 10px !important;
    }
    [data-testid="stSidebar"] input:focus {
        border-color: #0071e3 !important;
        box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.25) !important;
    }
    [data-testid="stSidebar"] button {
        background: rgba(255, 255, 255, 0.08) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 8px !important;
        color: #f5f5f7 !important;
        font-size: 0.78rem !important;
        font-weight: 500 !important;
        padding: 5px 12px !important;
        width: 100% !important;
        transition: all 0.15s ease !important;
    }
    [data-testid="stSidebar"] button:hover {
        background: rgba(255, 255, 255, 0.14) !important;
        border-color: rgba(255, 255, 255, 0.2) !important;
    }

    /* -------------------------------------------------------------
       5. Executive Apple Navigation Header
       ------------------------------------------------------------- */
    .apple-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        padding: 0.2rem 0 1.2rem 0;
        margin-bottom: 1.4rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        flex-wrap: wrap;
        gap: 14px;
    }
    .apple-title-group {
        display: flex;
        flex-direction: column;
        gap: 3px;
    }
    .apple-main-title {
        font-size: 1.65rem;
        font-weight: 600;
        letter-spacing: -0.025em;
        color: #ffffff;
        margin: 0;
        line-height: 1.2;
    }
    .apple-subtitle {
        font-size: 0.85rem;
        color: rgba(235, 235, 245, 0.55);
        margin: 0;
        font-weight: 400;
        letter-spacing: -0.01em;
    }
    .apple-pills-bar {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
    }
    .apple-capsule {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.76rem;
        font-weight: 500;
        letter-spacing: -0.01em;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.08);
        color: rgba(235, 235, 245, 0.8);
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
    }
    .apple-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        display: inline-block;
    }

    /* -------------------------------------------------------------
       6. Frosted Glass Cards (macOS Sonoma / VisionOS Material)
       ------------------------------------------------------------- */
    .glass-card {
        background: rgba(28, 30, 38, 0.55);
        backdrop-filter: blur(28px) saturate(180%);
        -webkit-backdrop-filter: blur(28px) saturate(180%);
        border: 1px solid rgba(255, 255, 255, 0.09);
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12), 0 8px 24px rgba(0, 0, 0, 0.32);
        border-radius: 16px;
        padding: 16px 14px;
        transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .glass-card:hover {
        transform: translateY(-2px);
        border-color: rgba(255, 255, 255, 0.16);
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18), 0 12px 30px rgba(0, 0, 0, 0.45);
    }
    .card-label {
        font-size: 0.74rem;
        font-weight: 500;
        color: rgba(235, 235, 245, 0.55);
        letter-spacing: -0.01em;
    }
    .card-value {
        font-size: 1.95rem;
        font-weight: 600;
        letter-spacing: -0.03em;
        line-height: 1.1;
        margin: 5px 0 3px 0;
    }
    .card-subtext {
        font-size: 0.74rem;
        color: rgba(235, 235, 245, 0.5);
        font-weight: 400;
        letter-spacing: -0.01em;
    }

    /* -------------------------------------------------------------
       7. Section Headers & Panels
       ------------------------------------------------------------- */
    .section-title {
        font-size: 0.95rem;
        font-weight: 600;
        letter-spacing: -0.01em;
        color: rgba(255, 255, 255, 0.9);
        margin: 0 0 10px 0;
    }

    .glass-panel {
        background: rgba(24, 26, 33, 0.5);
        backdrop-filter: blur(28px) saturate(180%);
        -webkit-backdrop-filter: blur(28px) saturate(180%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1), 0 10px 30px rgba(0, 0, 0, 0.3);
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 1.2rem;
    }

    /* Apple-style Architecture Grid */
    .specs-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin-top: 6px;
    }
    .spec-item {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 10px;
        padding: 10px 12px;
    }
    .spec-label {
        font-size: 0.68rem;
        color: rgba(235, 235, 245, 0.45);
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }
    .spec-val {
        font-size: 0.82rem;
        font-weight: 500;
        color: rgba(255, 255, 255, 0.85);
        margin-top: 2px;
        word-break: break-all;
    }

    /* Apple Alert Banner */
    .apple-alert {
        background: rgba(255, 159, 10, 0.08);
        border: 1px solid rgba(255, 159, 10, 0.22);
        border-radius: 12px;
        padding: 10px 16px;
        margin-bottom: 15px;
        color: #ff9f0a;
        font-size: 0.84rem;
        font-weight: 400;
        letter-spacing: -0.01em;
    }

    /* Apple Segmented Control for Radio Buttons */
    div[role="radiogroup"] {
        background: rgba(255, 255, 255, 0.05) !important;
        padding: 3px !important;
        border-radius: 9px !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        display: inline-flex !important;
        gap: 2px !important;
    }
    div[role="radiogroup"] label {
        margin: 0 !important;
        padding: 4px 10px !important;
        border-radius: 7px !important;
        font-size: 0.76rem !important;
        color: rgba(235, 235, 245, 0.7) !important;
    }
    </style>
""", unsafe_allow_html=True)

def load_log_data() -> pd.DataFrame or None:
    if not os.path.exists(CSV_PATH):
        return None
    try:
        df = pd.read_csv(CSV_PATH)
        if df.empty:
            return None
        return df
    except Exception:
        return None

def main():
    # ---------------------------------------------------------
    # SIDEBAR: macOS Style Settings Inspector
    # ---------------------------------------------------------
    st.sidebar.markdown("""
        <div style="padding-bottom: 10px; margin-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.08);">
            <div style="font-size: 1.05rem; font-weight: 600; color: #f5f5f7; letter-spacing: -0.02em;">Settings</div>
            <div style="font-size: 0.76rem; color: rgba(235,235,245,0.5);">Autonomous Thermal Policy</div>
        </div>
    """, unsafe_allow_html=True)
    
    # Reload config
    ctrl_settings = sys_config.get_controller_settings()
    thresholds = sys_config.get_thresholds()
    limits = sys_config.get_cpu_limits()
    sensor_cfg = sys_config.get_sensor_settings()
    
    st.sidebar.markdown("#### System Controls")
    ctrl_enabled = st.sidebar.toggle("Enable Autonomous Controller", value=ctrl_settings.get("enabled", True))
    dry_run_mode = st.sidebar.toggle("Dry Run (Telemetry Only)", value=ctrl_settings.get("dry_run", False))
    refresh_sec = st.sidebar.slider("Refresh Interval", min_value=1, max_value=10, value=2, format="%d s")
    
    if ctrl_enabled != ctrl_settings.get("enabled") or dry_run_mode != ctrl_settings.get("dry_run"):
        sys_config.set_controller_settings({"enabled": ctrl_enabled, "dry_run": dry_run_mode})
        st.sidebar.success("Settings updated")

    st.sidebar.markdown("---")
    st.sidebar.markdown("#### Operating Thresholds")
    cool_t = st.sidebar.slider("Cool Threshold", 60.0, 85.0, float(thresholds.get("cool_threshold", 80.0)), format="%.0f°C")
    bal_t = st.sidebar.slider("Balanced Threshold", 75.0, 92.0, float(thresholds.get("balanced_threshold", 90.0)), format="%.0f°C")
    boost_red_t = st.sidebar.slider("Boost Limit Threshold", 85.0, 98.0, float(thresholds.get("boost_reduction_threshold", 95.0)), format="%.0f°C")
    emerg_t = st.sidebar.slider("Emergency Threshold", 90.0, 100.0, float(thresholds.get("emergency_threshold", 95.0)), format="%.0f°C")
    
    if (cool_t != thresholds.get("cool_threshold") or bal_t != thresholds.get("balanced_threshold") or
        boost_red_t != thresholds.get("boost_reduction_threshold") or emerg_t != thresholds.get("emergency_threshold")):
        sys_config.set_thresholds({
            "cool_threshold": cool_t,
            "balanced_threshold": bal_t,
            "boost_reduction_threshold": boost_red_t,
            "emergency_threshold": emerg_t
        })

    st.sidebar.markdown("---")
    st.sidebar.markdown("#### Hysteresis Timing")
    hyster_sec = st.sidebar.slider("Transition Suppression", 0, 30, sys_config.get_hysteresis(), format="%d s")
    if hyster_sec != sys_config.get_hysteresis():
        sys_config.set_hysteresis(hyster_sec)

    st.sidebar.markdown("---")
    st.sidebar.markdown("#### Monitored Applications")
    current_games = sys_config.get_game_list()
    st.sidebar.caption(f"Configured Executables ({len(current_games)}):")
    st.sidebar.caption("`" + ", ".join(current_games[:5]) + ("...`" if len(current_games) > 5 else "`"))
    
    new_game = st.sidebar.text_input("Add Application Executable", placeholder="e.g. app.exe", key="add_game_input")
    if st.sidebar.button("Add Executable"):
        if new_game:
            sys_config.add_game(new_game)
            st.sidebar.success(f"Added {new_game}")
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("#### Diagnostics & Overrides")
    st.sidebar.caption("Manual override inputs for calibration testing.")
    
    sim_override_temp = st.sidebar.number_input("Manual Temp (°C, 0=Auto)", min_value=0.0, max_value=110.0, value=0.0)
    force_sim_mode = st.sidebar.checkbox("Force Simulation Telemetry", value=sensor_cfg.get("force_simulation", False))
    if force_sim_mode != sensor_cfg.get("force_simulation"):
        sys_config.set_sensor_settings({"force_simulation": force_sim_mode})

    # ---------------------------------------------------------
    # DATA LOADING & VALIDATION
    # ---------------------------------------------------------
    df = load_log_data()

    if df is None:
        st.markdown("""
            <div class="apple-alert">
                Telemetry logfile is initializing. Please ensure the controller runtime is active.
            </div>
        """, unsafe_allow_html=True)
        time.sleep(refresh_sec)
        st.rerun()
        return

    # Process DataFrame types safely
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["cpu_temp"] = pd.to_numeric(df["cpu_temp"], errors="coerce")
    df["gpu_temp"] = pd.to_numeric(df.get("gpu_temp", float("nan")), errors="coerce")
    df["cpu_usage"] = pd.to_numeric(df.get("cpu_usage", df.get("cpu_util", 0)), errors="coerce")
    df["gpu_usage"] = pd.to_numeric(df.get("gpu_usage", df.get("gpu_util", 0)), errors="coerce")
    df["ram_usage"] = pd.to_numeric(df.get("ram_usage", df.get("ram_util", 0)), errors="coerce")
    df["predicted_temp"] = pd.to_numeric(df.get("predicted_temp", df["cpu_temp"]), errors="coerce")
    df["cpu_limit"] = pd.to_numeric(df.get("cpu_limit", 100), errors="coerce").fillna(100)

    latest = df.iloc[-1]
    
    current_temp = float(latest["cpu_temp"])
    pred_temp = float(latest["predicted_temp"])
    temp_source = str(latest.get("temperature_source", "SIMULATION"))
    temp_backend = str(latest.get("temperature_backend", "Windows Kernel ACPI (\\_TZ.TZ01)"))
    pred_type = str(latest.get("prediction_type", "HEURISTIC / FALLBACK"))
    is_gaming = str(latest.get("is_gaming", False)).lower() in ("true", "1", "yes")
    game_name = str(latest.get("game_name", "None"))
    current_mode = str(latest.get("selected_mode", "balanced")).upper()
    is_emergency = bool(latest.get("emergency_override", False)) or current_temp >= emerg_t
    is_dryrun = dry_run_mode or str(latest.get("controller_status", "")).upper() == "DRY_RUN"

    # GPU Values
    latest_gpu_temp_raw = latest.get("gpu_temp")
    has_gpu_temp = pd.notna(latest_gpu_temp_raw) and latest_gpu_temp_raw != ""
    current_gpu_temp = float(latest_gpu_temp_raw) if has_gpu_temp else None

    latest_gpu_util_raw = latest.get("gpu_usage")
    has_gpu_util = pd.notna(latest_gpu_util_raw) and latest_gpu_util_raw != ""
    current_gpu_util = float(latest_gpu_util_raw) if has_gpu_util else 0.0

    # ---------------------------------------------------------
    # APPLE NAVIGATION HEADER
    # ---------------------------------------------------------
    pills_html = ""
    if not ctrl_enabled:
        pills_html += '<span class="apple-capsule"><span class="apple-dot" style="background:#ff9f0a;"></span>Paused</span>'
    elif is_emergency:
        pills_html += '<span class="apple-capsule" style="border-color:rgba(255,69,58,0.3); color:#ff453a;"><span class="apple-dot" style="background:#ff453a;"></span>Critical Thermal State</span>'
    elif is_dryrun:
        pills_html += '<span class="apple-capsule"><span class="apple-dot" style="background:#ff9f0a;"></span>Dry Run</span>'
    else:
        pills_html += '<span class="apple-capsule"><span class="apple-dot" style="background:#30d158;"></span>Active</span>'

    if temp_source == "REAL_HARDWARE":
        pills_html += '<span class="apple-capsule"><span class="apple-dot" style="background:#0a84ff;"></span>Hardware Sensor (Kernel Diode)</span>'
    else:
        pills_html += '<span class="apple-capsule"><span class="apple-dot" style="background:#ff9f0a;"></span>Simulation Mode</span>'

    if has_gpu_temp:
        pills_html += '<span class="apple-capsule"><span class="apple-dot" style="background:#bf5af2;"></span>NVIDIA RTX 4060</span>'

    st.markdown(f"""
        <div class="apple-header">
            <div class="apple-title-group">
                <h1 class="apple-main-title">Thermal Controller</h1>
                <div class="apple-subtitle">Predictive hardware telemetry and autonomous power scaling</div>
            </div>
            <div class="apple-pills-bar">
                {pills_html}
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Clean Callout Notice if in simulation
    if temp_source == "SIMULATION":
        st.markdown("""
            <div class="apple-alert">
                CPU telemetry is currently operating in simulation fallback mode. Direct kernel hardware diode (\\_TZ.TZ01) will engage automatically when real hardware sensors report. GPU telemetry is directly connected via NVIDIA NVML.
            </div>
        """, unsafe_allow_html=True)

    # ---------------------------------------------------------
    # ROW 1: APPLE FROSTED GLASS METRIC CARDS
    # ---------------------------------------------------------
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    
    # Apple System Colors: Muted Red, Orange, Green
    if current_temp >= emerg_t:
        temp_state_str = "Critical"
        t_color = "#ff453a"  # Apple Red
    elif current_temp >= bal_t:
        temp_state_str = "Elevated"
        t_color = "#ff9f0a"  # Apple Orange
    elif current_temp >= cool_t:
        temp_state_str = "Warm"
        t_color = "#ffd60a"  # Apple Yellow
    else:
        temp_state_str = "Normal"
        t_color = "#30d158"  # Apple Green

    delta_t = round(pred_temp - current_temp, 1)
    delta_str = f"+{delta_t}°C" if delta_t >= 0 else f"{delta_t}°C"

    with c1:
        st.markdown(f"""
            <div class="glass-card">
                <div class="card-label">CPU Temperature</div>
                <div class="card-value tabular-nums" style="color:{t_color};">{current_temp}°C</div>
                <div class="card-subtext">{temp_state_str}</div>
            </div>
        """, unsafe_allow_html=True)

    with c2:
        if current_gpu_temp is not None:
            gpu_color = "#30d158" if current_gpu_temp < 72 else ("#ff9f0a" if current_gpu_temp < 80 else "#ff453a")
            gpu_display = f"{current_gpu_temp}°C"
            gpu_sub = "NVIDIA NVML"
        else:
            gpu_color = "rgba(235, 235, 245, 0.5)"
            gpu_display = "Standby"
            gpu_sub = "Offline"

        st.markdown(f"""
            <div class="glass-card">
                <div class="card-label">GPU Temperature</div>
                <div class="card-value tabular-nums" style="color:{gpu_color};">{gpu_display}</div>
                <div class="card-subtext">{gpu_sub}</div>
            </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
            <div class="glass-card">
                <div class="card-label">10s Forecast</div>
                <div class="card-value tabular-nums" style="color:#bf5af2;">{pred_temp}°C</div>
                <div class="card-subtext">{delta_str} Horizon</div>
            </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
            <div class="glass-card">
                <div class="card-label">CPU Load</div>
                <div class="card-value tabular-nums" style="color:#64d2ff;">{latest["cpu_usage"]}%</div>
                <div class="card-subtext">Active Cores</div>
            </div>
        """, unsafe_allow_html=True)

    with c5:
        st.markdown(f"""
            <div class="glass-card">
                <div class="card-label">GPU Load</div>
                <div class="card-value tabular-nums" style="color:#ff9f0a;">{current_gpu_util}%</div>
                <div class="card-subtext">Graphics Engine</div>
            </div>
        """, unsafe_allow_html=True)

    with c6:
        st.markdown(f"""
            <div class="glass-card">
                <div class="card-label">Memory</div>
                <div class="card-value tabular-nums" style="color:#0a84ff;">{latest["ram_usage"]}%</div>
                <div class="card-subtext">RAM Committed</div>
            </div>
        """, unsafe_allow_html=True)

    with c7:
        clean_proc_name = game_name if is_gaming else "Desktop System"
        if len(clean_proc_name) > 13:
            clean_proc_name = clean_proc_name[:11] + "..."
        active_hw_plan = str(latest.get("power_plan", "Balanced")).title()
        st.markdown(f"""
            <div class="glass-card">
                <div class="card-label">Active State</div>
                <div class="card-value tabular-nums" style="font-size:1.15rem; color:#f5f5f7; padding-top:6px;">{clean_proc_name}</div>
                <div class="card-subtext">{active_hw_plan} ({latest.get('cpu_limit', 100)}%)</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ---------------------------------------------------------
    # ROW 2: MINIMALIST THERMAL GAUGES & TIME SERIES PROFILE
    # ---------------------------------------------------------
    g_col, chart_col = st.columns([1, 1.45])
    
    with g_col:
        st.markdown('<div class="section-title">Thermal Gauges</div>', unsafe_allow_html=True)
        gauge_c1, gauge_c2 = st.columns(2)
        
        with gauge_c1:
            fig_cpu_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = current_temp,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "CPU DIODE", 'font': {'size': 11, 'color': "rgba(235, 235, 245, 0.5)", 'family': '-apple-system, sans-serif'}},
                number = {'suffix': "°", 'font': {'color': t_color, 'size': 32, 'family': '-apple-system, sans-serif'}},
                gauge = {
                    'axis': {'range': [30, 105], 'tickwidth': 1, 'tickcolor': "rgba(255,255,255,0.15)", 'tickfont': {'color': 'rgba(235, 235, 245, 0.4)', 'size': 9}},
                    'bar': {'color': t_color, 'thickness': 0.22},
                    'bgcolor': "rgba(255,255,255,0.05)",
                    'borderwidth': 0,
                    'steps': [
                        {'range': [30, cool_t], 'color': 'rgba(48, 209, 88, 0.12)'},
                        {'range': [cool_t, bal_t], 'color': 'rgba(255, 159, 10, 0.12)'},
                        {'range': [bal_t, boost_red_t], 'color': 'rgba(255, 159, 10, 0.18)'},
                        {'range': [boost_red_t, 105], 'color': 'rgba(255, 69, 58, 0.22)'}
                    ],
                }
            ))
            fig_cpu_gauge.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=250,
                margin=dict(l=15, r=15, t=25, b=10)
            )
            st.plotly_chart(fig_cpu_gauge, use_container_width=True)

        with gauge_c2:
            gpu_val = current_gpu_temp if current_gpu_temp is not None else 45.0
            gpu_bar_color = "#30d158" if gpu_val < 72 else ("#ff9f0a" if gpu_val < 80 else "#ff453a")
            fig_gpu_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = gpu_val,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "GPU DIODE", 'font': {'size': 11, 'color': "rgba(235, 235, 245, 0.5)", 'family': '-apple-system, sans-serif'}},
                number = {'suffix': "°", 'font': {'color': gpu_bar_color, 'size': 32, 'family': '-apple-system, sans-serif'}},
                gauge = {
                    'axis': {'range': [30, 95], 'tickwidth': 1, 'tickcolor': "rgba(255,255,255,0.15)", 'tickfont': {'color': 'rgba(235, 235, 245, 0.4)', 'size': 9}},
                    'bar': {'color': gpu_bar_color, 'thickness': 0.22},
                    'bgcolor': "rgba(255,255,255,0.05)",
                    'borderwidth': 0,
                    'steps': [
                        {'range': [30, 70], 'color': 'rgba(48, 209, 88, 0.12)'},
                        {'range': [70, 80], 'color': 'rgba(255, 159, 10, 0.12)'},
                        {'range': [80, 87], 'color': 'rgba(255, 159, 10, 0.18)'},
                        {'range': [87, 95], 'color': 'rgba(255, 69, 58, 0.22)'}
                    ],
                }
            ))
            fig_gpu_gauge.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=250,
                margin=dict(l=15, r=15, t=25, b=10)
            )
            st.plotly_chart(fig_gpu_gauge, use_container_width=True)

    with chart_col:
        st.markdown('<div class="section-title">Temperature Profile & Forecast</div>', unsafe_allow_html=True)
        
        # Segmented Control Filter
        time_win = st.radio("Window", ["Last 1m", "Last 5m", "Last 15m", "Last 30m", "All Data"], index=1, horizontal=True, label_visibility="collapsed")
        
        plot_df = df.copy()
        if time_win == "Last 1m":
            plot_df = plot_df.tail(30)
        elif time_win == "Last 5m":
            plot_df = plot_df.tail(150)
        elif time_win == "Last 15m":
            plot_df = plot_df.tail(450)
        elif time_win == "Last 30m":
            plot_df = plot_df.tail(900)

        fig_live = go.Figure()
        
        # Actual CPU Temp line (Apple Green or Red if critical)
        fig_live.add_trace(go.Scatter(
            x=plot_df["timestamp"],
            y=plot_df["cpu_temp"],
            mode="lines",
            name="CPU Actual",
            line=dict(color=t_color, width=2.2, shape="spline"),
            hovertemplate="Time: %{x|%H:%M:%S}<br>CPU: <b>%{y}°C</b><extra></extra>"
        ))

        # Actual GPU Temp line
        if plot_df["gpu_temp"].dropna().any():
            fig_live.add_trace(go.Scatter(
                x=plot_df["timestamp"],
                y=plot_df["gpu_temp"],
                mode="lines",
                name="GPU Actual",
                line=dict(color="#ff9f0a", width=1.8, shape="spline"),
                hovertemplate="Time: %{x|%H:%M:%S}<br>GPU: <b>%{y}°C</b><extra></extra>"
            ))
        
        # Predicted CPU Temp line
        fig_live.add_trace(go.Scatter(
            x=plot_df["timestamp"],
            y=plot_df["predicted_temp"],
            mode="lines",
            name="AI Forecast (10s)",
            line=dict(color="#bf5af2", width=1.8, dash="dash", shape="spline"),
            hovertemplate="Time: %{x|%H:%M:%S}<br>Forecast: <b>%{y}°C</b><extra></extra>"
        ))
        
        # Minimalist threshold lines
        fig_live.add_hline(y=cool_t, line_dash="dot", line_color="rgba(48, 209, 88, 0.6)", line_width=1, annotation_text=f"Cool {cool_t}°", annotation_font_size=9, annotation_font_color="rgba(48, 209, 88, 0.7)", annotation_position="top left")
        fig_live.add_hline(y=bal_t, line_dash="dot", line_color="rgba(255, 159, 10, 0.6)", line_width=1, annotation_text=f"Balanced {bal_t}°", annotation_font_size=9, annotation_font_color="rgba(255, 159, 10, 0.7)", annotation_position="top left")
        if emerg_t == boost_red_t:
            fig_live.add_hline(y=emerg_t, line_dash="solid", line_color="rgba(255, 69, 58, 0.8)", line_width=1.2, annotation_text=f"Limit {emerg_t}°", annotation_font_size=9, annotation_font_color="rgba(255, 69, 58, 0.8)", annotation_position="top right")
        else:
            fig_live.add_hline(y=boost_red_t, line_dash="dash", line_color="rgba(255, 159, 10, 0.8)", line_width=1, annotation_text=f"Boost Cap {boost_red_t}°", annotation_font_size=9, annotation_font_color="rgba(255, 159, 10, 0.8)", annotation_position="bottom right")
            fig_live.add_hline(y=emerg_t, line_dash="solid", line_color="rgba(255, 69, 58, 0.8)", line_width=1.2, annotation_text=f"Emergency {emerg_t}°", annotation_font_size=9, annotation_font_color="rgba(255, 69, 58, 0.8)", annotation_position="top right")

        fig_live.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="-apple-system, sans-serif", color="rgba(235, 235, 245, 0.6)"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.06)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.06)", title="°C"),
            height=280,
            margin=dict(l=10, r=10, t=15, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0, 0, 0, 0)")
        )
        st.plotly_chart(fig_live, use_container_width=True)

    # ---------------------------------------------------------
    # ROW 3: PREDICTION ACCURACY ALIGNMENT
    # ---------------------------------------------------------
    st.markdown('<div class="section-title">Prediction Validation (10-Second Historical Alignment)</div>', unsafe_allow_html=True)
    
    df_eval = df.copy()
    # Align predictions: predicted temp at step i is compared to actual temp at step i+5 (~10s later)
    df_eval["actual_10s_later"] = df_eval["cpu_temp"].shift(-5)
    eval_df = df_eval.dropna(subset=["actual_10s_later", "predicted_temp"]).tail(60)

    if len(eval_df) > 5:
        fig_acc = go.Figure()
        fig_acc.add_trace(go.Scatter(
            x=eval_df["timestamp"],
            y=eval_df["actual_10s_later"],
            mode="lines",
            name="Actual (10s Later)",
            line=dict(color="#ff453a", width=1.8, shape="spline")
        ))
        fig_acc.add_trace(go.Scatter(
            x=eval_df["timestamp"],
            y=eval_df["predicted_temp"],
            mode="lines",
            name="AI Forecast Made",
            line=dict(color="#bf5af2", width=1.8, dash="dot", shape="spline")
        ))
        
        fig_acc.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="-apple-system, sans-serif", color="rgba(235, 235, 245, 0.6)"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.06)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.06)", title="°C"),
            height=230,
            margin=dict(l=10, r=10, t=15, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0, 0, 0, 0)")
        )
        st.plotly_chart(fig_acc, use_container_width=True)
    else:
        st.markdown('<div class="card-subtext">Calibrating rolling timeline for 10-second predictive alignment...</div>', unsafe_allow_html=True)

    # ---------------------------------------------------------
    # ROW 4: RESOURCE UTILIZATION & SYSTEM ARCHITECTURE
    # ---------------------------------------------------------
    c_left, c_right = st.columns(2)
    
    with c_left:
        st.markdown('<div class="section-title">Resource Utilization</div>', unsafe_allow_html=True)
        fig_res = go.Figure()
        fig_res.add_trace(go.Scatter(x=plot_df["timestamp"], y=plot_df["cpu_usage"], mode="lines", name="CPU", line=dict(color="#64d2ff", width=1.8, shape="spline")))
        if plot_df["gpu_usage"].dropna().any():
            fig_res.add_trace(go.Scatter(x=plot_df["timestamp"], y=plot_df["gpu_usage"], mode="lines", name="GPU", line=dict(color="#ff9f0a", width=1.8, shape="spline")))
        fig_res.add_trace(go.Scatter(x=plot_df["timestamp"], y=plot_df["ram_usage"], mode="lines", name="RAM", line=dict(color="#0a84ff", width=1.8, shape="spline")))
        fig_res.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="-apple-system, sans-serif", color="rgba(235, 235, 245, 0.6)"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.06)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.06)", range=[0, 105], title="%"),
            height=250,
            margin=dict(l=10, r=10, t=15, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0, 0, 0, 0)")
        )
        st.plotly_chart(fig_res, use_container_width=True)

    with c_right:
        st.markdown('<div class="section-title">System Architecture & Hardware</div>', unsafe_allow_html=True)
        st.markdown(f"""
            <div class="specs-grid">
                <div class="spec-item">
                    <div class="spec-label">GPU Acceleration</div>
                    <div class="spec-val">NVIDIA RTX 4060 Laptop GPU</div>
                </div>
                <div class="spec-item">
                    <div class="spec-label">GPU Telemetry Driver</div>
                    <div class="spec-val">Direct NVML (nvml.dll)</div>
                </div>
                <div class="spec-item">
                    <div class="spec-label">CPU Sensor Diode</div>
                    <div class="spec-val">{temp_backend}</div>
                </div>
                <div class="spec-item">
                    <div class="spec-label">Forecasting Model</div>
                    <div class="spec-val">Random Forest Regressor (10s Horizon)</div>
                </div>
                <div class="spec-item">
                    <div class="spec-label">Active Power Plan</div>
                    <div class="spec-val">{current_mode} ({latest.get('cpu_limit', 100)}% Throttle Cap)</div>
                </div>
                <div class="spec-item">
                    <div class="spec-label">Safety Controls</div>
                    <div class="spec-val">Hysteresis: {sys_config.get_hysteresis()}s • Failsafe Active</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # ---------------------------------------------------------
    # ROW 5: DECISION HISTORY
    # ---------------------------------------------------------
    st.markdown('<div class="section-title" style="margin-top:1.2rem;">Decision History</div>', unsafe_allow_html=True)
    show_cols = [c for c in ["timestamp", "cpu_temp", "gpu_temp", "temperature_source", "cpu_usage", "gpu_usage", "is_gaming", "game_name", "predicted_temp", "selected_mode", "cpu_limit", "action_taken"] if c in df.columns]
    log_show_df = df.tail(12).iloc[::-1][show_cols]
    st.dataframe(log_show_df, use_container_width=True)

    # Auto refresh loop
    time.sleep(refresh_sec)
    st.rerun()

if __name__ == "__main__":
    main()
