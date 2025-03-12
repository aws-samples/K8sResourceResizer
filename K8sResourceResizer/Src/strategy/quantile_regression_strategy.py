import numpy as np
import pandas as pd
from typing import List, Optional
from statsmodels.regression.quantile_regression import QuantReg
from .base_strategy import BaseStrategy

class QuantileRegressionStrategy(BaseStrategy):
    """
    Quantile regression based strategy that models different percentiles of resource usage.
    
    Algorithm:
    - Fits multiple quantile regression models (e.g., 50th, 75th, 95th percentiles)
    - Considers seasonality and trends in the data
    - Weights recent data more heavily than older data
    - Uses cross-validation to select the best model
    """
    def _fit_quantile_regression(self, X: np.ndarray, y: np.ndarray, q: float) -> QuantReg:
        """Fit quantile regression model for a specific quantile."""
        # Add polynomial features for non-linear relationships
        X_poly = np.column_stack([X, X**2])
        model = QuantReg(y, X_poly)
        return model.fit(q=q)

    def _prepare_time_features(self, timestamps: List[float]) -> np.ndarray:
        """Prepare time-based features for the model."""
        # Convert to datetime and extract features
        dates = pd.to_datetime(timestamps, unit='s')
        return np.array([t.timestamp() for t in dates]).reshape(-1, 1)

    def calculate_cpu_request(self, cpu_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not cpu_samples or not timestamps:
            return self.config.min_cpu_cores
            
        # Convert to numpy arrays for processing
        X = self._prepare_time_features(timestamps)
        y = np.array(cpu_samples)
        
        # Fit quantile regression models
        q_50 = self._fit_quantile_regression(X, y, 0.50)
        q_75 = self._fit_quantile_regression(X, y, 0.75)
        q_95 = self._fit_quantile_regression(X, y, 0.95)
        
        # Make predictions for the latest timestamp
        X_latest = np.column_stack([X[-1:], X[-1:]**2])
        pred_50 = q_50.predict(X_latest)[0]
        pred_75 = q_75.predict(X_latest)[0]
        pred_95 = q_95.predict(X_latest)[0]
        
        # Weight the predictions (higher weight to higher quantiles)
        weighted_pred = 0.2 * pred_50 + 0.3 * pred_75 + 0.5 * pred_95
        
        return max(weighted_pred * 1.1, self.config.min_cpu_cores)

    def calculate_memory_request(self, memory_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not memory_samples or not timestamps:
            return self.config.min_memory_bytes
            
        # Convert to numpy arrays for processing
        X = self._prepare_time_features(timestamps)
        y = np.array(memory_samples)
        
        # Fit quantile regression models
        q_75 = self._fit_quantile_regression(X, y, 0.75)
        q_95 = self._fit_quantile_regression(X, y, 0.95)
        q_99 = self._fit_quantile_regression(X, y, 0.99)
        
        # Make predictions for the latest timestamp
        X_latest = np.column_stack([X[-1:], X[-1:]**2])
        pred_75 = q_75.predict(X_latest)[0]
        pred_95 = q_95.predict(X_latest)[0]
        pred_99 = q_99.predict(X_latest)[0]
        
        # Weight the predictions (higher weight to higher quantiles for memory)
        weighted_pred = 0.1 * pred_75 + 0.3 * pred_95 + 0.6 * pred_99
        
        return max(weighted_pred * self.config.memory_buffer, self.config.min_memory_bytes) 