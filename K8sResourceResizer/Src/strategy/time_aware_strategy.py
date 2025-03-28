import numpy as np
import pandas as pd
from typing import List, Optional, Dict
from .base_strategy import BaseStrategy

class TimeAwareStrategy(BaseStrategy):
    """
    Time-aware resource recommendation strategy that considers business hours and patterns.
    
    Algorithm:
    - Analyzes usage patterns during business vs. non-business hours
    - CPU: Uses 95th percentile during business hours if usage differs by >20%
    - Memory: Uses peak usage during business hours if pattern exists
    - Applies different buffers based on time patterns
    - Considers day of week and hour of day in calculations
    """
    
    def calculate_cpu_request(self, cpu_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not cpu_samples or not timestamps:
            return self.config.min_cpu_cores
            
        patterns = self._analyze_time_patterns(cpu_samples, timestamps)
        
        # Use business hours p95 if there's significant difference
        if patterns['business_diff_ratio'] > 0.2:  # 20% difference threshold
            if patterns['business_hours_p95'] > 0:
                recommendation = patterns['business_hours_p95'] * 1.1
            else:
                recommendation = patterns['overall_p95'] * 1.1
        else:
            recommendation = patterns['overall_p95'] * 1.1
            
        return max(recommendation, self.config.min_cpu_cores)

    def calculate_memory_request(self, memory_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not memory_samples or not timestamps:
            return self.config.min_memory_bytes
            
        patterns = self._analyze_time_patterns(memory_samples, timestamps)
        
        # For memory, we care more about peak usage during business hours
        if patterns['business_diff_ratio'] > 0.2 and patterns['business_hours_peak'] > 0:
            recommendation = patterns['business_hours_peak'] * self.config.memory_buffer
        else:
            recommendation = patterns['overall_peak'] * self.config.memory_buffer
            
        return max(recommendation, self.config.min_memory_bytes)

    def _analyze_time_patterns(self, samples: List[float], timestamps: List[float]) -> Dict[str, float]:
        """
        Analyze time-based patterns in the usage data.
        
        Args:
            samples: List of usage samples
            timestamps: List of Unix timestamps
            
        Returns:
            Dict containing various time-based metrics
        """
        df = pd.DataFrame({
            'timestamp': pd.to_datetime(timestamps, unit='s'),
            'value': samples
        })
        
        # Convert timestamps to local time for accurate business hours
        df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert('Europe/Berlin')
        df['hour'] = df['timestamp'].dt.hour
        df['day'] = df['timestamp'].dt.dayofweek

        # Filter business hours with more precise time handling
        business_hours = df[
            (df['hour'] >= self.config.business_hours_start) & 
            (df['hour'] < self.config.business_hours_end) & 
            (df['day'].isin(self.config.business_days))
        ]
        
        non_business = df[~(
            (df['hour'] >= self.config.business_hours_start) & 
            (df['hour'] < self.config.business_hours_end) & 
            (df['day'].isin(self.config.business_days))
        )]
        
        # Calculate metrics with safeguards for empty dataframes
        business_mean = business_hours['value'].mean() if not business_hours.empty else 0
        non_business_mean = non_business['value'].mean() if not non_business.empty else 0
        overall_mean = df['value'].mean() if not df.empty else 0
        
        # Calculate the ratio of difference between business and non-business hours
        business_diff_ratio = abs(business_mean - non_business_mean) / overall_mean if overall_mean != 0 else 0
        
        return {
            'business_hours_p95': np.percentile(business_hours['value'], 95) if not business_hours.empty else 0,
            'business_hours_peak': business_hours['value'].max() if not business_hours.empty else 0,
            'non_business_p95': np.percentile(non_business['value'], 95) if not non_business.empty else 0,
            'overall_p95': np.percentile(df['value'], 95) if not df.empty else 0,
            'overall_peak': df['value'].max() if not df.empty else 0,
            'business_diff_ratio': business_diff_ratio,
            'business_mean': business_mean,
            'non_business_mean': non_business_mean
        } 