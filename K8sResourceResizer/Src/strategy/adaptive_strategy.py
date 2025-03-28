import numpy as np
import pandas as pd
from typing import List, Optional
from .base_strategy import BaseStrategy

class AdaptiveStrategy(BaseStrategy):
    """
    Adaptive resource recommendation strategy that combines multiple approaches.
    
    Algorithm:
    - CPU:
        - Checks for high variability (p99/p95 ratio)
        - Considers business hour patterns if present
        - Falls back to p95 with buffer if no patterns detected
    - Memory:
        - Handles spiky behavior with weighted average
        - Accounts for growth trends
        - Uses peak with buffer as baseline
    - Dynamically selects best approach based on usage characteristics
    """
    def calculate_cpu_request(self, cpu_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not cpu_samples:
            return self.config.min_cpu_cores
            
        p95 = np.percentile(cpu_samples, 95)
        p99 = np.percentile(cpu_samples, 99)
        
        # High variability check
        if p99 / p95 > 2:
            return max(p99 * 1.1, self.config.min_cpu_cores)
            
        # Check for time patterns if timestamps are provided
        if timestamps:
            time_patterns = self._analyze_time_patterns(cpu_samples, timestamps)
            if time_patterns['has_business_hours_pattern']:
                return max(time_patterns['business_hours_p95'] * 1.1, self.config.min_cpu_cores)
        
        # Default to p95 with buffer
        return max(p95 * 1.1, self.config.min_cpu_cores)

    def calculate_memory_request(self, memory_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not memory_samples:
            return self.config.min_memory_bytes
            
        peak = max(memory_samples)
        p95 = np.percentile(memory_samples, 95)
        
        # Check for spiky behavior
        if peak > p95 * 2:
            # Use weighted average of peak and p95
            return max((0.7 * peak + 0.3 * p95) * self.config.memory_buffer, 
                      self.config.min_memory_bytes)
        
        # Check for growth trend
        trend = self._analyze_trends(memory_samples)
        if trend['trend'] == 'increasing':
            return max(peak * (1 + trend['growth_rate']) * self.config.memory_buffer,
                      self.config.min_memory_bytes)
        
        # Default to peak with buffer
        return max(peak * self.config.memory_buffer, self.config.min_memory_bytes)

    def _analyze_time_patterns(self, samples: List[float], timestamps: List[float]) -> dict:
        df = pd.DataFrame({
            'timestamp': pd.to_datetime(timestamps, unit='s'),
            'value': samples
        })
        df['hour'] = df['timestamp'].dt.hour
        df['day'] = df['timestamp'].dt.dayofweek

        business_hours = df[
            (df['hour'] >= self.config.business_hours_start) & 
            (df['hour'] <= self.config.business_hours_end) & 
            (df['day'].isin(self.config.business_days))
        ]
        
        non_business = df[~(
            (df['hour'] >= self.config.business_hours_start) & 
            (df['hour'] <= self.config.business_hours_end) & 
            (df['day'].isin(self.config.business_days))
        )]
        
        business_mean = business_hours['value'].mean() if not business_hours.empty else 0
        non_business_mean = non_business['value'].mean() if not non_business.empty else 0
        
        return {
            'has_business_hours_pattern': abs(business_mean - non_business_mean) > business_mean * 0.2,
            'business_hours_p95': np.percentile(business_hours['value'], 95) if not business_hours.empty else 0,
            'overall_p95': np.percentile(df['value'], 95)
        }

    def _analyze_trends(self, samples: List[float]) -> dict:
        if len(samples) < 2:
            return {'trend': 'stable', 'growth_rate': 0}
            
        x = np.arange(len(samples))
        y = np.array(samples)
        slope, _ = np.polyfit(x, y, 1)
        
        growth_rate = (slope * len(samples)) / samples[0] if samples[0] != 0 else 0
        
        if growth_rate > self.config.trend_threshold:
            trend = 'increasing'
        elif growth_rate < -self.config.trend_threshold:
            trend = 'decreasing'
        else:
            trend = 'stable'
            
        return {'trend': trend, 'growth_rate': growth_rate} 