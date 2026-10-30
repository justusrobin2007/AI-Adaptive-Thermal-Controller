import os
import logging
import pandas as pd
import numpy as np
from datetime import datetime

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score
except ImportError:
    RandomForestRegressor = None
    mean_absolute_error = None
    root_mean_squared_error = None
    r2_score = None

logger = logging.getLogger("ThermalController.ML")

CSV_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
CSV_PATH = os.path.join(CSV_DIR, "thermal_log.csv")

class TemperaturePredictor:
    """
    Handles Random Forest temperature prediction and performance evaluation.
    Utilizes chronological time-series splitting for validation without data leakage.
    Calculates future targets by computing actual timestamp deltas (~10s horizon).
    """
    def __init__(self, csv_file_path: str = CSV_PATH):
        self.csv_path = csv_file_path
        self.model = None
        self.is_trained = False
        
        # Features used for prediction
        self.features = ["cpu_temp", "cpu_usage", "ram_usage", "is_gaming", "cpu_freq_mhz"]
        
        # Evaluation stats
        self.stats = {
            "is_trained": False,
            "prediction_type": "HEURISTIC / FALLBACK",
            "mae": None,
            "rmse": None,
            "r2": None,
            "training_samples": 0,
            "validation_samples": 0,
            "last_trained_time": "Never",
            "features_used": self.features,
            "horizon_seconds": 10
        }

    def train_model(self) -> bool:
        """
        Loads CSV logs, computes target temperature using timestamp deltas (~10s horizon),
        performs chronological time-series splitting (80% train / 20% val), and trains RandomForestRegressor.
        """
        if RandomForestRegressor is None:
            logger.warning("scikit-learn is not available. Predictor will operate in HEURISTIC / FALLBACK mode.")
            return False

        if not os.path.exists(self.csv_path):
            logger.info("Telemetry CSV log file not found. Predictor in HEURISTIC / FALLBACK mode.")
            return False

        try:
            df = pd.read_csv(self.csv_path)
            if len(df) < 25:
                logger.info(f"Insufficient telemetry logs for ML training ({len(df)}/25 rows required). Using HEURISTIC / FALLBACK.")
                return False

            # Type clean & sanitize
            df["cpu_temp"] = pd.to_numeric(df["cpu_temp"], errors="coerce")
            df["cpu_usage"] = pd.to_numeric(df.get("cpu_usage", df.get("cpu_util", 0)), errors="coerce")
            df["ram_usage"] = pd.to_numeric(df.get("ram_usage", df.get("ram_util", 0)), errors="coerce")
            df["cpu_freq_mhz"] = pd.to_numeric(df.get("cpu_freq_mhz", 2800), errors="coerce").fillna(2800)
            
            # Binary mapping for is_gaming
            df["is_gaming"] = df["is_gaming"].apply(lambda x: 1 if str(x).lower() in ("true", "1", "yes") else 0)
            
            # Clean missing values
            df = df.dropna(subset=["cpu_temp", "cpu_usage", "ram_usage"])
            if len(df) < 25:
                return False

            # Parse timestamps
            try:
                df["ts_dt"] = pd.to_datetime(df["timestamp"], errors="coerce")
                df["ts_sec"] = df["ts_dt"].apply(lambda t: t.timestamp() if pd.notnull(t) else np.nan)
                if df["ts_sec"].isna().any():
                    df["ts_sec"] = np.arange(len(df)) * 2.0
            except Exception:
                df["ts_sec"] = np.arange(len(df)) * 2.0

            # Compute actual 10-second future temperature targets using timestamp deltas
            target_temps = []
            valid_indices = []
            
            ts_array = df["ts_sec"].values
            temp_array = df["cpu_temp"].values
            n_rows = len(df)
            
            for i in range(n_rows):
                t_curr = ts_array[i]
                found = False
                for j in range(i + 1, n_rows):
                    dt = ts_array[j] - t_curr
                    if dt >= 8.0:
                        target_temps.append(temp_array[j])
                        valid_indices.append(i)
                        found = True
                        break

            if len(valid_indices) >= 15:
                dataset_df = df.iloc[valid_indices].copy()
                dataset_df["target_cpu_temp"] = target_temps
            else:
                # Index-based shift fallback if timestamp deltas are sparse
                df["target_cpu_temp"] = df["cpu_temp"].shift(-5)
                dataset_df = df.dropna(subset=["target_cpu_temp"]).copy()

            X = dataset_df[self.features]
            y = dataset_df["target_cpu_temp"]

            # Chronological Time-Series Split (First 80% Train, Last 20% Validation)
            split_idx = int(len(dataset_df) * 0.8)
            
            X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
            y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

            if len(X_train) < 15:
                return False

            # Train Random Forest Regressor
            rf = RandomForestRegressor(n_estimators=40, max_depth=5, random_state=42)
            rf.fit(X_train, y_train)

            # Evaluate on chronological validation set
            mae, rmse, r2 = None, None, None
            if len(X_val) > 0:
                y_pred_val = rf.predict(X_val)
                mae = round(float(mean_absolute_error(y_val, y_pred_val)), 2)
                rmse = round(float(root_mean_squared_error(y_val, y_pred_val)), 2)
                r2 = round(float(r2_score(y_val, y_pred_val)), 3)

            self.model = rf
            self.is_trained = True
            
            self.stats = {
                "is_trained": True,
                "prediction_type": "ML FORECAST",
                "mae": mae,
                "rmse": rmse,
                "r2": r2,
                "training_samples": len(X_train),
                "validation_samples": len(X_val),
                "last_trained_time": datetime.now().strftime("%H:%M:%S"),
                "features_used": self.features,
                "horizon_seconds": 10
            }
            logger.info(f"RandomForest model trained successfully on {len(X_train)} samples! Val MAE: {mae}°C, RMSE: {rmse}°C, R²: {r2}")
            return True

        except Exception as e:
            logger.error(f"Error training ML model: {e}")
            return False

    def predict_temp(self, current_state_dict: dict) -> tuple:
        """
        Predicts temperature ~10s in the future.
        
        Returns:
            (predicted_temp: float, prediction_type: str)
            prediction_type is 'ML FORECAST' or 'HEURISTIC / FALLBACK'
        """
        current_temp = float(current_state_dict.get("cpu_temp", 50.0))
        cpu_usage = float(current_state_dict.get("cpu_usage", current_state_dict.get("cpu_util", 0.0)))
        ram_usage = float(current_state_dict.get("ram_usage", current_state_dict.get("ram_util", 0.0)))
        cpu_freq = float(current_state_dict.get("cpu_freq_mhz", 2800.0))
        is_gaming_raw = current_state_dict.get("is_gaming", False)
        is_gaming = 1 if str(is_gaming_raw).lower() in ("true", "1", "yes") else 0

        # Attempt Random Forest prediction
        if self.is_trained and self.model is not None:
            try:
                X_pred = pd.DataFrame([{
                    "cpu_temp": current_temp,
                    "cpu_usage": cpu_usage,
                    "ram_usage": ram_usage,
                    "is_gaming": is_gaming,
                    "cpu_freq_mhz": cpu_freq
                }])
                pred = self.model.predict(X_pred[self.features])[0]
                return round(float(pred), 1), "ML FORECAST"
            except Exception as e:
                logger.error(f"RandomForest inference failed: {e}. Falling back to physics estimator.")

        # Smart Thermodynamic Fallback Estimator (HEURISTIC / FALLBACK)
        load_factor = cpu_usage / 100.0
        gaming_bonus = 2.2 if is_gaming else 0.0
        
        if cpu_usage > 75:
            temp_change = (load_factor * 3.8) + gaming_bonus
        elif cpu_usage < 25:
            temp_change = -1.6
        else:
            temp_change = 0.4 + gaming_bonus

        predicted = current_temp + temp_change
        predicted = max(35.0, min(102.0, predicted))
        return round(predicted, 1), "HEURISTIC / FALLBACK"

    def get_model_stats(self) -> dict:
        """Returns metadata regarding model accuracy, dataset sizes, and prediction type."""
        return self.stats
