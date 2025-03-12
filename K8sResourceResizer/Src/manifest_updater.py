"""
Manifest updater for Kubernetes resource configurations.

This module handles the process of updating resource configurations in:
1. Helm value files
2. Kustomize patches and resources

Key functionalities:
- Processing deployments to identify resource files
- Updating CPU and memory limits/requests in manifests
- Supporting both Helm and Kustomize manifest formats
- Preserving file formatting and structure
"""

import os
from typing import Optional, Tuple, List, Dict, Any
from logger import logger
from argocd_client import get_argocd_instance, get_argocd_app_git_path
import yaml
from manifest_finder import find_helm_resource_files, find_kustomize_resource_files
from utils import handle_exceptions
import json

@handle_exceptions
def process_deployments(recommendations: dict, base_dir: str) -> list[dict]:
    """
    Process deployments and update their resource configurations.
    
    Args:
        recommendations: Dictionary of resource recommendations
        base_dir: Base directory containing manifests
        
    Returns:
        list[dict]: List of updated deployments with their file paths
    """
    if not recommendations:
        logger.warning("No recommendations provided, skipping deployment processing")
        return []

    # Extract new limits and requests from recommendations
    new_limits = {}
    new_requests = {}
    updated_deployments = []
    
    logger.debug(f"Full recommendations structure: {json.dumps(recommendations, indent=2)}")

    # Process each container's recommendations
    for full_key, data in recommendations.items():
        if not data or 'recommended' not in data:
            logger.debug(f"No recommendations for {full_key}, skipping")
            continue
            
        recommended = data['recommended']
        
        # Extract limits
        limits = recommended.get('limits', {})
        if limits:
            new_limits[full_key] = {
                k: str(v['value']) for k, v in limits.items() 
                if v['value'] is not None
            }
            logger.debug(f"Extracted limits for {full_key}: {new_limits[full_key]}")
        
        # Extract requests
        requests = recommended.get('requests', {})
        if requests:
            new_requests[full_key] = {
                k: str(v['value']) for k, v in requests.items()
                if v['value'] is not None
            }
            logger.debug(f"Extracted requests for {full_key}: {new_requests[full_key]}")
    
    if not new_limits and not new_requests:
        logger.warning("No valid recommendations found to process")
        return []

    # Get all deployments from recommendations
    recommendation_deployments = {
        tuple(key.split('/')[:2])  # Only take namespace and deployment name
        for key in recommendations.keys()
    }
    logger.debug(f"Recommendation deployments: {recommendation_deployments}")
    
    # Get all ArgoCD applications
    argocd_apps = get_argocd_instance()
    if not argocd_apps:
        logger.warning("No ArgoCD applications found")
        return []
    
    # Get deployments from ArgoCD apps
    argocd_deployments = set()
    for app in argocd_apps:
        resources = app.get('status', {}).get('resources', [])
        for resource in resources:
            if resource.get('kind') == 'Deployment':
                argocd_deployments.add((
                    resource['namespace'],
                    resource['name']
                ))
    
    logger.debug(f"Found ArgoCD deployments: {argocd_deployments}")
    
    # Find intersection of deployments
    deployments_to_process = recommendation_deployments & argocd_deployments
    logger.debug(f"Intersection result: {deployments_to_process}")
    
    # Process intersecting deployments
    for namespace, name in deployments_to_process:
        deployment_key = f"{namespace}/{name}"
        logger.debug(f"Processing deployment: {deployment_key}")
        
        # Get the deployment data from recommendations
        deployment_data = next(
            (data['object'] for key, data in recommendations.items() 
             if key.startswith(f"{deployment_key}/")),
            None
        )
        
        if not deployment_data:
            logger.warning(f"Could not find deployment data for {deployment_key}")
            continue
        
        # Find the corresponding ArgoCD app
        app = next((app for app in argocd_apps 
                   if any(resource['kind'] == 'Deployment' 
                         and resource['namespace'] == namespace 
                         and resource['name'] == name 
                         for resource in app.get('status', {}).get('resources', []))), None)
        
        if not app:
            logger.warning(f"Could not find ArgoCD app for deployment {deployment_key}")
            continue
        
        # Filter limits and requests for just this deployment
        filtered_limits = {
            container_key: limits 
            for container_key, limits in new_limits.items()
            if container_key.startswith(f"{deployment_key}/")
        }
        
        filtered_requests = {
            container_key: requests 
            for container_key, requests in new_requests.items()
            if container_key.startswith(f"{deployment_key}/")
        }
        
        # Get app source info
        source = app.get('spec', {}).get('source', {})
        if not source:
            logger.warning(f"No source information found for app {app.get('metadata', {}).get('name')}")
            continue

        # Determine if it's a Helm or Kustomize app
        is_helm = bool(source.get('helm'))
        app_path = source.get('path', '')

        if is_helm:
            helm_values = source.get('helm', {}).get('valueFiles', [])
            logger.debug(f"Processing Helm app with values: {helm_values}")
            resource_file = find_helm_resource_files(base_dir, app_path, helm_values, name)
        else:  # kustomize
            logger.debug(f"Processing Kustomize app at path: {app_path}")
            resource_file = find_kustomize_resource_files(base_dir, app_path, name)
        
        if resource_file:
            logger.info(f"Found resource file at: {resource_file}")
            # Convert values to Kubernetes-friendly units
            converted_limits, converted_requests = convert_resource_values(
                filtered_limits,
                filtered_requests
            )
            try:
                update_manifest_with_new_resources(
                    resource_file, 
                    converted_limits,
                    converted_requests
                )
                # Create updated deployment object with file path
                updated_deployment = deployment_data.copy()
                updated_deployment['updated_file'] = resource_file
                updated_deployment['recommendations'] = {
                    'limits': converted_limits,
                    'requests': converted_requests
                }
                updated_deployments.append(updated_deployment)
                logger.info(f"Updated resources in {resource_file} for deployment {deployment_key}")
            except Exception as e:
                logger.error(f"Failed to update {resource_file}: {e}")
        else:
            logger.warning(f"No resource file found for deployment {deployment_key}")

    logger.info(f"Successfully updated {len(updated_deployments)} deployments")
    return updated_deployments

@handle_exceptions
def update_manifest_with_new_resources(file_path: str, new_limits: dict, new_requests: dict) -> None:
    """
    Update resource limits and requests in a manifest file.
    Preserves file structure and only updates values after the colon.
    """
    logger.debug(f"Updating manifest file: {file_path}")
    logger.debug(f"New limits: {new_limits}")
    logger.debug(f"New requests: {new_requests}")
    
    updated_lines = []
    in_resources = False
    in_limits = False
    in_requests = False
    
    with open(file_path, 'r') as file:
        for line in file:
            # Track which section we're in
            if 'resources:' in line:
                in_resources = True
            elif in_resources and line.strip() == '':
                in_resources = False
                in_limits = False
                in_requests = False
            elif in_resources and 'limits:' in line:
                in_limits = True
                in_requests = False
            elif in_resources and 'requests:' in line:
                in_requests = True
                in_limits = False
            
            # Update values if we're in the right section
            if in_limits and new_limits:
                if 'cpu:' in line:
                    line = line.split('cpu:')[0] + f"cpu: {new_limits['cpu']}\n"
                elif 'memory:' in line:
                    line = line.split('memory:')[0] + f"memory: {new_limits['memory']}\n"
            elif in_requests and new_requests:
                if 'cpu:' in line:
                    line = line.split('cpu:')[0] + f"cpu: {new_requests['cpu']}\n"
                elif 'memory:' in line:
                    line = line.split('memory:')[0] + f"memory: {new_requests['memory']}\n"
            
            updated_lines.append(line)
    
    with open(file_path, 'w') as file:
        file.writelines(updated_lines)
    
    logger.debug(f"Successfully updated manifest: {file_path}")

@handle_exceptions
def has_resource_definitions(file_path: str) -> bool:
    """Check if a file contains resource definitions."""
    with open(file_path, 'r') as f:
        content = yaml.safe_load(f)
        if not content:
            return False
        
        # Check for resources in different formats
        if isinstance(content, dict):
            # Check for direct resources key
            if 'resources' in content:
                return True
            
            # Check in spec.template.spec.containers[].resources
            containers = content.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
            for container in containers:
                if 'resources' in container:
                    return True
            
            # Check in spec.containers[].resources
            containers = content.get('spec', {}).get('containers', [])
            for container in containers:
                if 'resources' in container:
                    return True
        
        return False

def convert_resource_values(limits: dict, requests: dict) -> Tuple[dict, dict]:
    """
    Convert CPU and memory values to Kubernetes-friendly units.
    CPU: cores -> millicores (m)
    Memory: bytes -> MiB
    """
    converted_limits = {}
    converted_requests = {}
    
    # Convert limits for the first container
    if limits:
        first_container = next(iter(limits.values()))
        if 'cpu' in first_container:
            try:
                cpu_value = float(first_container['cpu'])
                converted_limits['cpu'] = f"{int(cpu_value * 1000)}m"
            except (ValueError, TypeError):
                logger.warning(f"Invalid CPU limit value: {first_container['cpu']}")
        
        if 'memory' in first_container:
            try:
                memory_value = float(first_container['memory'])
                converted_limits['memory'] = f"{int(memory_value / (1024 * 1024))}Mi"
            except (ValueError, TypeError):
                logger.warning(f"Invalid memory limit value: {first_container['memory']}")
    
    # Convert requests for the first container
    if requests:
        first_container = next(iter(requests.values()))
        if 'cpu' in first_container:
            try:
                cpu_value = float(first_container['cpu'])
                converted_requests['cpu'] = f"{int(cpu_value * 1000)}m"
            except (ValueError, TypeError):
                logger.warning(f"Invalid CPU request value: {first_container['cpu']}")
        
        if 'memory' in first_container:
            try:
                memory_value = float(first_container['memory'])
                converted_requests['memory'] = f"{int(memory_value / (1024 * 1024))}Mi"
            except (ValueError, TypeError):
                logger.warning(f"Invalid memory request value: {first_container['memory']}")
    
    return converted_limits, converted_requests
