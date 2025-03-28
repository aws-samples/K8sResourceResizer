from . import RecommendationStrategy, RecommendationConfig
from .basic_strategy import BasicStrategy
from .time_aware_strategy import TimeAwareStrategy
from .trend_aware_strategy import TrendAwareStrategy
from .workload_aware_strategy import WorkloadAwareStrategy
from .adaptive_strategy import AdaptiveStrategy
from .quantile_regression_strategy import QuantileRegressionStrategy
from .moving_average_strategy import MovingAverageStrategy
from .pmdarima_strategy import PMDARIMAStrategy
from .prophet_strategy import ProphetStrategy
from .ensemble_strategy import EnsembleStrategy

class StrategyFactory:
    @staticmethod
    def create_strategy(config: RecommendationConfig):
        strategies = {
            RecommendationStrategy.BASIC: BasicStrategy,
            RecommendationStrategy.TIME_AWARE: TimeAwareStrategy,
            RecommendationStrategy.TREND_AWARE: TrendAwareStrategy,
            RecommendationStrategy.WORKLOAD_AWARE: WorkloadAwareStrategy,
            RecommendationStrategy.ADAPTIVE: AdaptiveStrategy,
            RecommendationStrategy.QUANTILE_REGRESSION: QuantileRegressionStrategy,
            RecommendationStrategy.MOVING_AVERAGE: MovingAverageStrategy,
            RecommendationStrategy.PMDARIMA: PMDARIMAStrategy,
            RecommendationStrategy.PROPHET: ProphetStrategy,
            RecommendationStrategy.ENSEMBLE: EnsembleStrategy
        }
        
        strategy_class = strategies.get(config.strategy)
        if not strategy_class:
            raise ValueError(f"Unknown strategy: {config.strategy}")
        
        return strategy_class(config) 