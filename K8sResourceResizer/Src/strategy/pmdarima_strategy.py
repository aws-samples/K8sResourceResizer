import numpy as np
import pandas as pd
from typing import List, Optional
from .base_strategy import BaseStrategy
from pmdarima import auto_arima
from pmdarima.arima.utils import ndiffs
from loguru import logger
import warnings
from functools import lru_cache

# Filter out specific scikit-learn deprecation warnings
warnings.filterwarnings('ignore', category=FutureWarning)

class PMDARIMAStrategy(BaseStrategy):
    """
    PMDARIMA-based strategy for automatic ARIMA modeling.
    
    Optimized for speed:
    - Limited parameter search space
    - Parallel execution when possible
    - Quick ADF test for differencing
    - Memory caching for repeated patterns
    - LRU cache for time series preparation
    - Early stopping for model selection
    - Downsampling for long series
    """
    def __init__(self, config):
        super().__init__(config)
        self.forecast_steps = 12  # 1-hour prediction window
        self.seasonal = True      # Enable seasonal patterns
        self.seasonal_period = 12 # 1-hour seasonality (with 5-min intervals)
        self._model_cache = {}    # Cache for similar patterns
        self.max_series_length = 500  # Maximum length for time series

    @lru_cache(maxsize=1000)
    def _get_cache_key(self, stats_tuple: tuple) -> str:
        """Generate cache key based on series characteristics."""
        return str(hash(stats_tuple))

    def _prepare_time_series(self, samples: List[float], timestamps: List[float]) -> pd.Series:
        """Prepare time series data for ARIMA modeling with downsampling."""
        df = pd.DataFrame({
            'timestamp': pd.to_datetime(timestamps, unit='s'),
            'value': samples
        })
        df.set_index('timestamp', inplace=True)

        # Downsample if series is too long
        if len(df) > self.max_series_length:
            # Calculate appropriate frequency to get desired length
            freq = int(len(df) / self.max_series_length)
            df = df.rolling(window=freq, min_periods=1).mean().iloc[::freq]
            logger.debug(f"Downsampled series from {len(samples)} to {len(df)} points")

        return df['value']

    def _get_series_stats(self, series: pd.Series) -> tuple:
        """Get statistical features of the series."""
        # Use faster numpy operations
        values = series.values
        return (
            float(np.mean(values)),
            float(np.std(values)),
            float(np.percentile(values, 95)),
            len(values),
            bool(np.any(np.isnan(values)))
        )

    def _fit_and_predict(self, series: pd.Series) -> tuple[float, float]:
        """Fit ARIMA model and make prediction with confidence interval."""
        try:
            # Check cache first using statistical features
            stats = self._get_series_stats(series)
            cache_key = self._get_cache_key(stats)
            
            if cache_key in self._model_cache:
                model = self._model_cache[cache_key]
                logger.debug("Using cached model")
            else:
                # Quick differencing test with early stopping
                n_diffs = min(ndiffs(series, alpha=0.05, test='adf', max_d=2), 1)
                
                # Fit auto ARIMA model with optimized settings
                model = auto_arima(
                    series,
                    start_p=0,        # Start with simpler models
                    start_q=0,
                    max_p=2,
                    max_q=2,
                    max_d=n_diffs,
                    m=self.seasonal_period if self.seasonal else 1,
                    seasonal=self.seasonal,
                    D=1 if self.seasonal else None,
                    max_P=1,
                    max_Q=1,
                    trace=False,
                    error_action='ignore',
                    suppress_warnings=True,
                    stepwise=True,
                    n_jobs=-1,
                    random_state=42,
                    maxiter=10,
                    information_criterion='aic',  # Faster than bic
                    method='lbfgs',              # Faster optimization
                    with_intercept=True,         # Allow intercept for better fit
                    max_order=4                  # Limit total parameters
                )
                
                # Cache the model
                self._model_cache[cache_key] = model
                
                # Limit cache size with LRU policy
                if len(self._model_cache) > 100:
                    oldest_key = min(self._model_cache.keys(), key=lambda k: self._model_cache[k].fit_time_)
                    self._model_cache.pop(oldest_key)
            
            # Make prediction with confidence interval
            forecast, conf_int = model.predict(
                n_periods=self.forecast_steps,
                return_conf_int=True,
                alpha=0.05
            )
            
            return forecast[-1], conf_int[-1][1]
            
        except Exception as e:
            logger.warning(f"ARIMA model fitting failed: {str(e)}")
            return None, None

    def calculate_cpu_request(self, cpu_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not cpu_samples or not timestamps:
            return self.config.min_cpu_cores
            
        try:
            # Prepare time series
            series = self._prepare_time_series(cpu_samples, timestamps)
            
            # Get prediction and confidence interval
            prediction, upper_bound = self._fit_and_predict(series)
            
            if prediction is not None and upper_bound is not None:
                # Use upper bound for conservative estimation
                recommended = upper_bound
            else:
                # Fallback to percentile
                recommended = np.percentile(cpu_samples, 95)
            
            return max(recommended * 1.1, self.config.min_cpu_cores)
            
        except Exception as e:
            logger.warning(f"CPU prediction failed: {str(e)}. Falling back to percentile.")
            return max(np.percentile(cpu_samples, 95) * 1.1, self.config.min_cpu_cores)

    def calculate_memory_request(self, memory_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not memory_samples or not timestamps:
            return self.config.min_memory_bytes
            
        try:
            # Prepare time series
            series = self._prepare_time_series(memory_samples, timestamps)
            
            # Get prediction and confidence interval
            prediction, upper_bound = self._fit_and_predict(series)
            
            if prediction is not None and upper_bound is not None:
                # Use upper bound with memory buffer
                recommended = upper_bound * self.config.memory_buffer
            else:
                # Fallback to peak usage
                recommended = max(memory_samples) * self.config.memory_buffer
            
            return max(recommended, self.config.min_memory_bytes)
            
        except Exception as e:
            logger.warning(f"Memory prediction failed: {str(e)}. Falling back to peak usage.")
            return max(max(memory_samples) * self.config.memory_buffer, self.config.min_memory_bytes) 