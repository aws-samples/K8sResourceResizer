import numpy as np
from typing import List, Optional, Dict
from .base_strategy import BaseStrategy
from .basic_strategy import BasicStrategy
from .time_aware_strategy import TimeAwareStrategy
from .workload_aware_strategy import WorkloadAwareStrategy
from .trend_aware_strategy import TrendAwareStrategy
from .quantile_regression_strategy import QuantileRegressionStrategy
from .moving_average_strategy import MovingAverageStrategy
# Removed pmdarima due to extremely slow performance in production environments
# from .pmdarima_strategy import PMDARIMAStrategy
from .prophet_strategy import ProphetStrategy

class EnsembleStrategy(BaseStrategy):
    """
    Ensemble strategy that combines predictions from multiple models.
    
    Algorithm:
    - Runs multiple strategies in parallel
    - Weights predictions based on historical accuracy
    - Uses voting for final recommendation
    - Adapts weights based on performance
    
    Note: PMDARima strategy has been removed due to extremely slow performance
    in production environments. While it can provide good predictions, its
    computational overhead makes it impractical for real-time resource optimization.
    """
    def __init__(self, config):
        super().__init__(config)
        # Initialize all strategies
        self.strategies = {
            'basic': BasicStrategy(config),
            'time_aware': TimeAwareStrategy(config),
            'workload_aware': WorkloadAwareStrategy(config),
            'trend_aware': TrendAwareStrategy(config),
            'quantile_regression': QuantileRegressionStrategy(config),
            'moving_average': MovingAverageStrategy(config),
            'prophet': ProphetStrategy(config)
        }
        # Initial weights (equal weighting)
        self.weights = {name: 1.0/len(self.strategies) for name in self.strategies.keys()}
        self.prediction_history = []

    def _get_weighted_prediction(self, predictions: Dict[str, float]) -> float:
        """Calculate weighted average of predictions."""
        return sum(
            predictions[name] * self.weights[name]
            for name in predictions.keys()
        )

    def _update_weights(self, actual: float, predictions: Dict[str, float]):
        """Update strategy weights based on prediction accuracy."""
        errors = {
            name: abs(pred - actual) / actual if actual != 0 else abs(pred)
            for name, pred in predictions.items()
        }
        # Convert errors to weights (lower error = higher weight)
        total_error = sum(errors.values())
        if total_error > 0:
            new_weights = {
                name: (1 - error/total_error) 
                for name, error in errors.items()
            }
            # Normalize weights
            weight_sum = sum(new_weights.values())
            self.weights = {
                name: weight/weight_sum 
                for name, weight in new_weights.items()
            }

    def calculate_cpu_request(self, cpu_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not cpu_samples or not timestamps:
            return self.config.min_cpu_cores
            
        # Get predictions from all strategies
        predictions = {}
        for name, strategy in self.strategies.items():
            try:
                pred = strategy.calculate_cpu_request(cpu_samples, timestamps)
                predictions[name] = pred
            except Exception as e:
                # If a strategy fails, use the minimum value
                predictions[name] = self.config.min_cpu_cores
        
        # Calculate weighted prediction
        weighted_pred = self._get_weighted_prediction(predictions)
        
        # Add some safety margin
        return max(weighted_pred * 1.1, self.config.min_cpu_cores)

    def calculate_memory_request(self, memory_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not memory_samples or not timestamps:
            return self.config.min_memory_bytes
            
        # Get predictions from all strategies
        predictions = {}
        for name, strategy in self.strategies.items():
            try:
                pred = strategy.calculate_memory_request(memory_samples, timestamps)
                predictions[name] = pred
            except Exception as e:
                # If a strategy fails, use the minimum value
                predictions[name] = self.config.min_memory_bytes
        
        # Calculate weighted prediction
        weighted_pred = self._get_weighted_prediction(predictions)
        
        # Apply memory buffer
        return max(weighted_pred * self.config.memory_buffer, self.config.min_memory_bytes) 