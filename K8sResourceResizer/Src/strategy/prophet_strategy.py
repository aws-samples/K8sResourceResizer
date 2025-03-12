import numpy as np
import pandas as pd
from typing import List, Optional
from .base_strategy import BaseStrategy
from prophet import Prophet
from loguru import logger

class ProphetStrategy(BaseStrategy):
    """
    Prophet-based forecasting strategy for resource prediction.
    
    Algorithm:
    - Uses Facebook's Prophet for time series forecasting
    - Handles seasonality, holidays, and trend changes
    - CPU: Uses multiplicative seasonality for percentage-based metrics
    - Memory: Uses additive seasonality for absolute values
    - Includes uncertainty intervals for conservative estimates
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.forecast_steps = 12  # 1-hour prediction window
        self._model_cache = {}    # Cache for similar patterns
        
    def _prepare_prophet_data(self, samples: List[float], timestamps: List[float]) -> pd.DataFrame:
        """Prepare data in Prophet's required format."""
        return pd.DataFrame({
            'ds': pd.to_datetime(timestamps, unit='s'),
            'y': samples
        })
        
    def _fit_prophet_model(self, df: pd.DataFrame, multiplicative_seasonality: bool = False) -> Prophet:
        """Fit Prophet model with optimized parameters."""
        model = Prophet(
            interval_width=0.95,           # 95% confidence interval
            growth='linear',               # Linear growth
            daily_seasonality=True,        # Daily patterns
            weekly_seasonality=True,       # Weekly patterns
            yearly_seasonality=False,      # No yearly patterns (not enough data)
            seasonality_mode='multiplicative' if multiplicative_seasonality else 'additive',
            changepoint_prior_scale=0.05,  # More flexible trend changes
            seasonality_prior_scale=10.0,  # Stronger seasonality
            changepoint_range=0.9,         # Allow changes up until 90% of the data
            n_changepoints=25              # Number of potential changepoints
        )
        
        # Add business hours seasonality
        model.add_seasonality(
            name='business_hours',
            period=24,
            fourier_order=5,
            condition_name='is_business_hour'
        )
        
        # Add business hours condition
        df['is_business_hour'] = (
            (df['ds'].dt.hour >= self.config.business_hours_start) &
            (df['ds'].dt.hour < self.config.business_hours_end) &
            (df['ds'].dt.dayofweek.isin(self.config.business_days))
        )
        
        try:
            model.fit(df)
            return model
        except Exception as e:
            logger.warning(f"Prophet model fitting failed: {str(e)}")
            return None
            
    def calculate_cpu_request(self, cpu_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not cpu_samples or not timestamps:
            return self.config.min_cpu_cores
            
        try:
            # Prepare data
            df = self._prepare_prophet_data(cpu_samples, timestamps)
            
            # Fit model with multiplicative seasonality for CPU
            model = self._fit_prophet_model(df, multiplicative_seasonality=True)
            if not model:
                return max(np.percentile(cpu_samples, 95) * 1.1, self.config.min_cpu_cores)
            
            # Make future dataframe for prediction
            future = model.make_future_dataframe(
                periods=self.forecast_steps,
                freq='5min',
                include_history=False
            )
            
            # Add business hours condition to future
            future['is_business_hour'] = (
                (future['ds'].dt.hour >= self.config.business_hours_start) &
                (future['ds'].dt.hour < self.config.business_hours_end) &
                (future['ds'].dt.dayofweek.isin(self.config.business_days))
            )
            
            # Make prediction
            forecast = model.predict(future)
            
            # Use upper bound of the prediction interval
            recommended = forecast['yhat_upper'].max()
            
            return max(recommended * 1.1, self.config.min_cpu_cores)
            
        except Exception as e:
            logger.warning(f"CPU prediction failed: {str(e)}. Falling back to percentile.")
            return max(np.percentile(cpu_samples, 95) * 1.1, self.config.min_cpu_cores)
            
    def calculate_memory_request(self, memory_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not memory_samples or not timestamps:
            return self.config.min_memory_bytes
            
        try:
            # Prepare data
            df = self._prepare_prophet_data(memory_samples, timestamps)
            
            # Fit model with additive seasonality for memory
            model = self._fit_prophet_model(df, multiplicative_seasonality=False)
            if not model:
                return max(max(memory_samples) * self.config.memory_buffer, self.config.min_memory_bytes)
            
            # Make future dataframe for prediction
            future = model.make_future_dataframe(
                periods=self.forecast_steps,
                freq='5min',
                include_history=False
            )
            
            # Add business hours condition to future
            future['is_business_hour'] = (
                (future['ds'].dt.hour >= self.config.business_hours_start) &
                (future['ds'].dt.hour < self.config.business_hours_end) &
                (future['ds'].dt.dayofweek.isin(self.config.business_days))
            )
            
            # Make prediction
            forecast = model.predict(future)
            
            # Use upper bound of the prediction interval with memory buffer
            recommended = forecast['yhat_upper'].max() * self.config.memory_buffer
            
            return max(recommended, self.config.min_memory_bytes)
            
        except Exception as e:
            logger.warning(f"Memory prediction failed: {str(e)}. Falling back to peak usage.")
            return max(max(memory_samples) * self.config.memory_buffer, self.config.min_memory_bytes) 