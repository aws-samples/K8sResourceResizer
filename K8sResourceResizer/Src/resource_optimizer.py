"""
Resource Optimizer for Kubernetes.

This module provides functionality to:
1. Query AMP metrics for CPU and memory usage
2. Generate resource recommendations based on usage patterns
3. Save recommendations for further processing
"""

from datetime import datetime, timedelta
import numpy as np
import json
import os
from severity import Severity
from logger import logger
from typing import Optional
from amp_client import AMP
from utils import handle_exceptions, ensure_directory_exists
from strategy import BasicStrategy

class ResourceOptimizer:
    def __init__(self, workspace_id: str, region: str, strategy: 'BasicStrategy'):
        """
        Initialize the resource optimizer.
        
        Args:
            workspace_id: AMP workspace ID
            region: AWS region
            strategy: Strategy instance for generating recommendations
        """
        logger.info("Initializing resource optimizer")
        self.amp = AMP(workspace_id, region)
        self.strategy = strategy
        logger.info(f"Successfully initialized resource optimizer with strategy: {strategy.__class__.__name__}")

    @handle_exceptions
    def get_deployments(self) -> list:
        """Get all deployments in the cluster."""
        logger.info("Getting all deployments in the cluster")
        query = 'kube_deployment_spec_replicas != 0'
        result = self.amp.query(query)
        
        deployments = [
            {
                'namespace': deployment['metric']['namespace'],
                'name': deployment['metric']['deployment']
            }
            for deployment in result['data']['result']
        ]
        
        logger.info(f"Found {len(deployments)} deployments")
        return deployments

    @handle_exceptions
    def get_historical_usage(self, namespace: str, deployment: str, container: str) -> dict:
        """Get historical CPU and memory usage for a deployment."""
        logger.debug(f"Getting historical usage for {deployment} in {namespace}")
        
        # Get current time and calculate time window
        end_time = datetime.now()
        history_hours = self.strategy.config.history_window_hours
        # Get 24 hours of data for better pattern detection
        start_time = end_time - timedelta(hours=history_hours)

        logger.debug(f"Using time window of {history_hours} hours")
        logger.debug(f"Time range: from {start_time} to {end_time}")
        
        # CPU usage query with rate over 5m to smooth spikes
        cpu_query = f'''sum(rate(container_cpu_usage_seconds_total{{
            namespace="{namespace}",
            pod=~"{deployment}-[a-z0-9]+-[a-z0-9]+",
            container="{container}"
        }}[5m])) by (container)'''
        
        # Memory usage query
        memory_query = f'''sum(container_memory_working_set_bytes{{
            namespace="{namespace}",
            pod=~"{deployment}-[a-z0-9]+-[a-z0-9]+",
            container="{container}"
        }}) by (container)'''
        
        # Convert to Unix timestamps for AMP API
        start_timestamp = int(start_time.timestamp())
        end_timestamp = int(end_time.timestamp())
        
        # Get historical data
        cpu_data = self.amp.query_range(
            query=cpu_query,
            start=start_timestamp,
            end=end_timestamp,
            step='5m'
        )
        
        memory_data = self.amp.query_range(
            query=memory_query,
            start=start_timestamp,
            end=end_timestamp,
            step='5m'
        )
        
        # Extract values and timestamps
        cpu_samples = []
        memory_samples = []
        timestamps = []
        
        if cpu_data.get('data', {}).get('result'):
            for point in cpu_data['data']['result'][0]['values']:
                timestamps.append(float(point[0]))
                cpu_samples.append(float(point[1]))
                
        if memory_data.get('data', {}).get('result'):
            for point in memory_data['data']['result'][0]['values']:
                memory_samples.append(float(point[1]))
                
        return {
            'cpu_samples': cpu_samples,
            'memory_samples': memory_samples,
            'timestamps': timestamps
        }

    def _determine_severity(self, current: Optional[float], recommended: Optional[float]) -> Severity:
        """Determine severity level based on difference between current and recommended values."""
        if current is None and recommended is None:
            return Severity.GOOD
        if current is None or recommended is None:
            return Severity.WARNING

        diff = abs(current - recommended) / current
        if diff >= 0.5:  # 50% difference
            return Severity.CRITICAL
        elif diff >= 0.25:  # 25% difference
            return Severity.WARNING
        elif diff >= 0.1:  # 10% difference
            return Severity.OK
        else:
            return Severity.GOOD

    def _validate_cpu_request(self, cpu_cores: float) -> float:
        """Validate CPU request according to K8s best practices."""
        # Minimum of 10m (0.01 cores)
        MIN_CPU = 0.01
        # Maximum of 64 cores (typical node CPU limit)
        MAX_CPU = 64.0
        
        return max(MIN_CPU, min(cpu_cores, MAX_CPU))

    def _validate_memory_request(self, memory_bytes: float) -> float:
        """Validate memory request according to K8s best practices."""
        # Minimum of 32Mi
        MIN_MEMORY = 32 * 1024 * 1024
        # Maximum of 256Gi (typical node memory limit)
        MAX_MEMORY = 256 * 1024 * 1024 * 1024
        
        return max(MIN_MEMORY, min(memory_bytes, MAX_MEMORY))

    def _calculate_cpu_limit(self, cpu_request: float) -> float:
        """Calculate CPU limit based on request following K8s best practices."""
        if cpu_request < 0.1:  # For small containers (<100m)
            # Use 3x for small containers to allow bursting
            limit = cpu_request * 3.0
        elif cpu_request < 1.0:  # For medium containers (<1 core)
            # Use 2.5x for medium containers
            limit = cpu_request * 2.5
        else:  # For large containers (>=1 core)
            # Use 2x for large containers
            limit = cpu_request * 2.0
        
        return self._validate_cpu_request(limit)

    def _calculate_memory_limit(self, memory_request: float) -> float:
        """Calculate memory limit based on request following K8s best practices."""
        # For small containers (<256Mi)
        if memory_request < 256 * 1024 * 1024:
            # Use 1.5x for small containers
            limit = memory_request * 1.5
        else:
            # Use 1.3x for larger containers
            limit = memory_request * 1.3
        
        return self._validate_memory_request(limit)

    @handle_exceptions
    def generate_recommendations(self) -> dict:
        """Generate resource recommendations using the configured strategy."""
        logger.info("Generating recommendations for all deployments")
        
        # Get all deployments
        deployments = self.get_deployments()
        
        # Get recommendations for each deployment
        recommendations = {}
        for deployment in deployments:
            namespace = deployment['namespace']
            name = deployment['name']
            deployment_key = f"{namespace}/{name}"
            
            # Get containers in deployment
            query = f'''kube_pod_container_info{{
                namespace="{namespace}",
                pod=~"{name}-[a-z0-9]+-[a-z0-9]+"
            }}'''
            result = self.amp.query(query)
            
            containers = list({
                container['metric']['container']
                for container in result['data']['result']
            })
            
            logger.info(f"Found {len(containers)} containers in deployment {name}")
            
            # Get recommendations for each container
            for container in containers:
                usage = self.get_historical_usage(namespace, name, container)
                
                # Calculate and validate requests
                cpu_request = self._validate_cpu_request(
                    self.strategy.calculate_cpu_request(
                        usage['cpu_samples'],
                        usage['timestamps']
                    )
                )
                memory_request = self._validate_memory_request(
                    self.strategy.calculate_memory_request(
                        usage['memory_samples'],
                        usage['timestamps']
                    )
                )
                
                # Calculate limits based on validated requests
                cpu_limit = self._calculate_cpu_limit(cpu_request)
                memory_limit = self._calculate_memory_limit(memory_request)
                
                container_key = f"{deployment_key}/{container}"
                recommendations[container_key] = {
                    'object': {
                        'namespace': namespace,
                        'name': name,
                        'container': container
                    },
                    'recommended': {
                        'requests': {
                            'cpu': {
                                'value': cpu_request,
                                'severity': self._determine_severity(None, cpu_request)
                            },
                            'memory': {
                                'value': memory_request,
                                'severity': self._determine_severity(None, memory_request)
                            }
                        },
                        'limits': {
                            'cpu': {
                                'value': cpu_limit,
                                'severity': self._determine_severity(None, cpu_limit)
                            },
                            'memory': {
                                'value': memory_limit,
                                'severity': self._determine_severity(None, memory_limit)
                            }
                        }
                    }
                }
        
        logger.info(f"Generated recommendations for {len(recommendations)} containers")
        return recommendations

    @handle_exceptions
    def prepare_recommendations_to_save(self, recommendations: dict, updated_deployments: list[dict] = None) -> dict:
        """
        Prepare recommendations data structure for saving.
        
        Args:
            recommendations: Dictionary of resource recommendations
            updated_deployments: List of updated deployments with their file paths
            
        Returns:
            dict: Structured recommendations data with metadata
        """
        # Get strategy description from docstring
        if self.strategy.__doc__:
            paragraphs = [p.strip() for p in self.strategy.__doc__.split('\n\n') if p.strip()]
            strategy_description = paragraphs[0] if paragraphs else ""
        else:
            strategy_description = ""
        
        # Create metadata section
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "strategy": {
                "name": self.strategy.config.strategy.value,
                "description": strategy_description,
                "config": {
                    "cpu_percentile": self.strategy.config.cpu_percentile,
                    "memory_buffer": self.strategy.config.memory_buffer,
                    "history_window_hours": self.strategy.config.history_window_hours,
                    "business_hours": {
                        "start": self.strategy.config.business_hours_start,
                        "end": self.strategy.config.business_hours_end,
                        "days": self.strategy.config.business_days
                    }
                }
            },
            "updated_deployments": updated_deployments or []
        }
        
        # Create the final output structure
        return {
            "metadata": metadata,
            "recommendations": recommendations
        }