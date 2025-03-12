import numpy as np
import pandas as pd
from typing import List, Optional
from .base_strategy import BaseStrategy

class MovingAverageStrategy(BaseStrategy):
    """
    Moving Average based strategy for time series forecasting.
    
    Algorithm:
    - Uses exponential weighted moving average (EWMA)
    - Considers multiple window sizes for short and long-term patterns
    - Calculates prediction intervals using rolling standard deviation
    - Adapts to trend changes using momentum indicators
    """
    def _calculate_ewma(self, series: pd.Series, spans: List[int]) -> List[float]:
        """Calculate exponential weighted moving averages for multiple spans."""
        return [series.ewm(span=span, adjust=False).mean().iloc[-1] for span in spans]

    def _calculate_prediction_interval(self, series: pd.Series, confidence: float = 0.95) -> float:
        """Calculate prediction interval using rolling statistics."""
        # Calculate rolling standard deviation
        rolling_std = series.rolling(window=min(len(series), 12)).std().iloc[-1]
        # Use t-distribution for small samples
        from scipy import stats
        t_value = stats.t.ppf((1 + confidence) / 2, df=len(series)-1)
        return rolling_std * t_value

    def calculate_cpu_request(self, cpu_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not cpu_samples:
            return self.config.min_cpu_cores
            
        # Convert to pandas series
        series = pd.Series(cpu_samples)
        
        # Calculate multiple EWMAs
        short_term = self._calculate_ewma(series, [6])[0]  # 30-minute window
        medium_term = self._calculate_ewma(series, [12])[0]  # 1-hour window
        long_term = self._calculate_ewma(series, [24])[0]  # 2-hour window
        
        # Weight the different terms (favor recent data)
        weighted_avg = 0.5 * short_term + 0.3 * medium_term + 0.2 * long_term
        
        # Add prediction interval
        prediction_interval = self._calculate_prediction_interval(series)
        recommended = weighted_avg + prediction_interval
        
        return max(recommended * 1.1, self.config.min_cpu_cores)

    def calculate_memory_request(self, memory_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not memory_samples:
            return self.config.min_memory_bytes
            
        # Convert to pandas series
        series = pd.Series(memory_samples)
        
        # Calculate multiple EWMAs with longer windows for memory
        medium_term = self._calculate_ewma(series, [24])[0]  # 2-hour window
        long_term = self._calculate_ewma(series, [48])[0]  # 4-hour window
        
        # Weight the different terms (favor longer-term stability for memory)
        weighted_avg = 0.4 * medium_term + 0.6 * long_term
        
        # Add prediction interval with higher confidence for memory
        prediction_interval = self._calculate_prediction_interval(series, confidence=0.99)
        recommended = weighted_avg + prediction_interval
        
        return max(recommended * self.config.memory_buffer, self.config.min_memory_bytes) 