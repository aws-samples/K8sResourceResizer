from collections import defaultdict
import yaml

python_incontext_learning = """
Example:
Application: in-context-learning-example

Recommendations:
```
{
    "timestamp": "2025-02-14T15:22:12.738073",
    "strategy": {
      "name": "ensemble",
      "description": "Ensemble strategy that combines predictions from multiple models.\n    \n    Algorithm:\n    - Runs multiple strategies in parallel\n    - Weights predictions based on historical accuracy\n    - Uses voting for final recommendation\n    - Adapts weights based on performance\n    \n    Note: PMDARima strategy has been removed due to extremely slow performance\n    in production environments. While it can provide good predictions, its\n    computational overhead makes it impractical for real-time resource optimization.",
      "config": {
        "cpu_percentile": 95.0,
        "memory_buffer": 1.15,
        "history_window_hours": 24,
        "business_hours": {
          "start": 9,
          "end": 17,
          "days": [
            0,
            1,
            2,
            3,
            4
          ]
        }
      }
    },
    "updated_deployments": [
      {
        "namespace": "hello-world",
        "name": "prod-hello-world",
        "container": "hello-world",
        "updated_file": "/Users/hcayada/Code/argocd-stub-repo/kustomize/hello-world/overlay/production/memory_limit.yaml",
        "recommendations": {
          "limits": {
            "cpu": "3660m",
            "memory": "2660Mi"
          },
          "requests": {
            "cpu": "1830m",
            "memory": "2046Mi"
          }
        }
      },
      {
        "namespace": "hello-world-production",
        "name": "hello-helm-world-production-hello-world-chart",
        "container": "hello-world-chart",
        "updated_file": "/Users/hcayada/Code/argocd-stub-repo/helm/hello-world/environments/production.yaml",
        "recommendations": {
          "limits": {
            "cpu": "5625m",
            "memory": "2197Mi"
          },
          "requests": {
            "cpu": "2812m",
            "memory": "1690Mi"
          }
        }
      }
    ]
}
```

Resource Optimization Strategies:
```
## Basic Strategy
Simple statistical analysis using percentiles and standard deviations of historical resource usage. Best for workloads with stable, consistent resource patterns.
- Uses: Mean, median, and percentile calculations
- Good for: Stable applications with predictable resource usage
- Limitations: Doesn't account for time patterns or trends

## Time-Aware Strategy
Analyzes resource usage patterns based on business hours vs. non-business hours, recognizing that applications often have different resource needs during working hours.
- Uses: Time-based segmentation of metrics
- Good for: Applications with clear business-hour patterns
- Considers: Defined business hours, weekdays vs. weekends
- Limitations: May not catch seasonal or monthly patterns

## Trend-Aware Strategy
Identifies long-term resource usage trends, helping predict future needs based on historical growth or reduction patterns.
- Uses: Linear regression and trend analysis
- Good for: Applications with steady growth or seasonal patterns
- Considers: Weekly, monthly, and quarterly trends
- Limitations: May be sensitive to outliers

## Workload-Aware Strategy
Analyzes different types of workload patterns (batch jobs, web services, etc.) and their specific resource usage characteristics.
- Uses: Pattern recognition and workload classification
- Good for: Mixed workload environments
- Considers: Peak usage periods, idle times, and burst patterns
- Limitations: Requires sufficient historical data to identify patterns

## Quantile Regression Strategy
Advanced statistical modeling that focuses on different percentiles of resource usage, providing more nuanced recommendations.
- Uses: Quantile regression analysis
- Good for: Applications with variable resource usage
- Considers: Multiple percentiles for better accuracy
- Limitations: Computationally more intensive

## Moving Average Strategy
Time series analysis using different types of moving averages to smooth out short-term fluctuations.
- Uses: Simple, weighted, and exponential moving averages
- Good for: Noisy data with short-term variations
- Considers: Recent trends with configurable time windows
- Limitations: May lag behind sudden changes

## Prophet Strategy
Implements Facebook's Prophet forecasting tool for sophisticated time series predictions.
- Uses: Facebook's Prophet algorithm
- Good for: Complex seasonal patterns and holiday effects
- Considers: Multiple seasonality, holidays, and trends
- Limitations: Requires more computational resources

## Ensemble Strategy
Combines predictions from multiple strategies using weighted averaging for more robust recommendations.
- Uses: Weighted combination of all other strategies
- Good for: Production environments requiring high reliability
- Considers: Confidence levels from each strategy
- Limitations: May be more conservative in its recommendations
```

Original production.yaml before we apply resource optimization recommendations:
```
environment: production

replicaCount: 3

image:
  tag: "latest"
  pullPolicy: Always

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 200m
    memory: 256Mi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 6 
```

Updated production.yaml after we apply resource optimization recommendations:

```
environment: production

replicaCount: 3

image:
  tag: "latest"
  pullPolicy: Always

resources:
  limits:
    cpu: 5625m  
    memory: 2197Mi
  requests:
    cpu: 2812m
    memory: 1690Mi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 6 
```

Original memory_limit.yaml before we apply resource optimization recommendations:

```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello-world
spec:
  template:
    spec:
      containers:
        - name: hello-world
          resources:
            limits:
              memory: "512Mi"
            requests:
              memory: "128Mi"
```

Updated memory_limit.yaml after we apply resource optimization recommendations:
```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello-world
spec:
  template:
    spec:
      containers:
        - name: hello-world
          resources:
            limits:
              cpu: "3660m"
              memory: "2660Mi"
            requests:
              cpu: "1830m"
              memory: "2046Mi"
```

Task:
```
1. From the recommendations JSON object get the "updated_deployments" array and for each object of the array; from the "updated_file" value get the namespace, name, file names, and the environment name. For urls that include the substring "kustomize" you can get the environment variable after the "overlay". For example  from "/overlay/production/" the environment is "production. Don't mention the full path of the files.

2. From the recommendations JSON object, get the "strategy.name" value and use the matching strategy from the "Resource Optimization Strategies" to explain it.

3. From the recommendations JSON object, mention also "history_window_hours" value and the period of "business_hours" that are taken into account

4. Check the original and updates kubernetes manifests files, and compare and explain the changes of values

Please provide your explanations for the recommendations in the following format:

The Resource Optimization Automation for EKS has identified these optimizations:

## Strategy Name: 
<brief explanation>

##History window hours and business_hours taken into account # 
<brief explanation>

# Changes to files
- file name: <file name>
  namespace: <updated_deployments.namespace>
  deployment name: <updated_deployments.name>
  environment name: <environment name> 
  
  <brief explanation of changes for each file>

Remember to thoroughly test your application after implementing these changes to ensure all functionalities remain intact.
```
---
Prompt for the model:
"""

def build_model_prompt(recommendations, repo_name):
    """
    Build the model prompt for Bedrock with inputs from recommendation, instructions, and updated manifest files
    """

    updated_file_paths_relative = get_updated_file_paths_relative(recommendations)
    updated_file_contents = get_updated_file_contents(recommendations)
    
    prompt = f"Application: {repo_name}\n\Recommendations:\n"
    prompt += f"Recommendations: {recommendations}\n"
    prompt += f"- Updated kubernetes manifest file location: {updated_file_paths_relative}\n"
    prompt += f"  Updated kubernetes manifest file content: {updated_file_contents}\n"
    prompt += f"Analyze the recommendations and the updated kubernetes manifest files with the new resource usage values according to the example and instructions below.\n"
    
    return prompt

def get_updated_file_paths(recommendations):
    # Initialize an empty list to store the values
    updated_file_paths = []
    for deployment in recommendations['metadata']['updated_deployments']:
      updated_file_paths.append(deployment['updated_file'])
    
    return updated_file_paths

def get_updated_file_paths_relative(recommendations):
    # Initialize an empty list to store the values
    updated_file_paths_relative = []
    for deployment in recommendations['metadata']['updated_deployments']:
      values_file_path_relative = deployment['updated_file'].split(f"/app/manifests/", 1)[1]
      updated_file_paths_relative.append(values_file_path_relative)
    
    return updated_file_paths_relative

def get_updated_file_contents(recommendations):
    # Initialize an empty list to store the values
    updated_file_content = []
    for deployment in recommendations['metadata']['updated_deployments']: 
      with open(deployment['updated_file'], 'r') as file:
        updated_file_content.append(yaml.safe_load(file))

    return updated_file_content