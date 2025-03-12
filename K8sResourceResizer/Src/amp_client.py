"""
Amazon Managed Prometheus (AMP) client.

This module handles interactions with AMP to:
1. Query instant metrics about resource usage
2. Execute range queries for historical data
3. Authenticate requests using AWS SigV4

Key features:
- AWS authentication handling
- Prometheus query execution
- Error handling and retries
- Metric data parsing
"""

import requests
from requests_aws4auth import AWS4Auth
from botocore.session import Session
from datetime import datetime, timedelta
from logger import logger
from utils import handle_exceptions

class AMP:
    @handle_exceptions
    def __init__(self, workspace_id: str, region: str):
        logger.debug(f"Initializing AMP client with workspace_id: {workspace_id}, region: {region}")
        self.region = region
        self.workspace_id = workspace_id
        self.base_url = f"https://aps-workspaces.{region}.amazonaws.com/workspaces/{workspace_id}"
        logger.debug(f"AMP base URL: {self.base_url}")
        
        # Verify credentials on initialization
        self._auth()
        logger.debug("Successfully initialized AMP client with valid credentials")

    @handle_exceptions
    def _auth(self):
        """Create sigv4 auth for requests."""
        logger.debug("Creating AWS SigV4 authentication")
        credentials = Session().get_credentials()
        if not credentials:
            raise ValueError("No AWS credentials found")
        
        auth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            self.region,
            'aps',
            session_token=credentials.token
        )
        logger.debug("Successfully created AWS SigV4 authentication")
        return auth

    @handle_exceptions
    def query(self, query: str):
        """Execute an instant query"""
        endpoint = f"{self.base_url}/api/v1/query"
        params = {'query': query}
        logger.debug(f"Executing instant query: {query}")

        response = requests.get(
            url=endpoint,
            auth=self._auth(),
            params=params,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        logger.debug(f"Query successful, result status: {result.get('status', 'unknown')}")
        return result

    @handle_exceptions
    def query_range(self, query: str, start: float, end: float, step: str):
        """
        Execute a range query from start to end time.
        
        Args:
            query: The PromQL query to execute
            start: Unix timestamp for start time (in seconds)
            end: Unix timestamp for end time (in seconds)
            step: Step interval for data points (e.g., '5m' for 5-minute intervals)
        """
        endpoint = f"{self.base_url}/api/v1/query_range"
        
        params = {
            'query': query,
            'start': start,
            'end': end,
            'step': step
        }
        logger.debug(f"Executing range query: {query}")
        logger.debug(f"Time range: {datetime.fromtimestamp(start)} to {datetime.fromtimestamp(end)}, step: {step}")

        response = requests.get(
            url=endpoint,
            auth=self._auth(),
            params=params,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        data_points = len(result.get('data', {}).get('result', [{}])[0].get('values', []))
        logger.debug(f"Range query successful, received {data_points} data points")
        return result

    @handle_exceptions
    def get_pod_names(self, namespace: str, deployment: str) -> list:
        """Get list of pod names for a deployment."""
        logger.debug(f"Getting pod names for deployment {deployment} in namespace {namespace}")
        query = f'''kube_pod_info{{
            namespace="{namespace}",
            pod=~"{deployment}-[a-z0-9]+-[a-z0-9]+"
        }}'''
        
        response = self.query(query)
        pods = [{"name": pod["metric"]["pod"]} for pod in response["data"]["result"]]
        
        logger.debug(f"Found {len(pods)} pods for deployment {deployment}")
        return pods

    @handle_exceptions
    def get_cluster_name(self) -> str:
        """Get the EKS cluster ARN."""
        logger.debug("Querying for EKS cluster name")
        query = 'kube_node_labels{label_eks_amazonaws_com_cluster!=""}'
        response = self.query(query)
        
        if not response["data"]["result"]:
            logger.warning("No cluster name found in node labels")
            return ""
            
        cluster_name = response["data"]["result"][0]["metric"]["label_eks_amazonaws_com_cluster"]
        logger.debug(f"Found cluster name: {cluster_name}")
        return cluster_name 