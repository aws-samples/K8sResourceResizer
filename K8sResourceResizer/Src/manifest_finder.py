"""
Resource manifest finder for Kubernetes configurations.

This module is responsible for locating resource configuration files in:
1. Helm charts (values.yaml files)
2. Kustomize overlays (patches and resources)

Key functionalities:
- Recursive searching in Kustomize bases
- Support for both .yaml and .yml extensions
- Validation of resource definitions
- Error handling for malformed YAML
"""

import os
import yaml
import json
from logger import logger
from typing import List, Optional, Dict
from utils import handle_exceptions


@handle_exceptions
def get_yaml_files(directory: str) -> List[str]:
    """
    Fetch all YAML files in a directory.
    """
    logger.info(f"🤖 Fetching all files in dir: {directory}")
    yaml_files = [
        os.path.join(root, file)
        for root, _, files in os.walk(directory)
        for file in files
        if file.endswith((".yaml", ".yml"))
    ]
    logger.debug(f"🤖 Found {len(yaml_files)} YAML files")
    return yaml_files


@handle_exceptions
def parse_yaml(files: List[str]) -> List[dict]:
    """
    Parse YAML files into dictionaries.
    """
    resources = []
    for file_path in files:
        logger.debug(f"Processing file: {file_path}")
        with open(file_path, "r") as f:
            documents = list(yaml.safe_load_all(f))
            for doc in documents:
                if doc is not None:
                    resources.append(doc)
    return resources


@handle_exceptions
def parse_selector(selector: Optional[str]) -> Dict[str, str]:
    """
    Parse a text-based selector in the format 'key=value'.
    """
    if not selector:
        return {}

    key, value = selector.split("=")
    return {key.strip(): value.strip()}


@handle_exceptions
def get_applications(resources: List[dict], selector: Optional[str] = None) -> List[dict]:
    """
    Filter and return applications from K8s resources based on the selector.
    """
    applications = []
    parsed_selector = parse_selector(selector)

    for resource in resources:
        kind = resource.get("kind")
        if kind not in ["Application", "ApplicationSet"]:
            continue

        metadata = resource.get("metadata", {})
        labels = metadata.get("labels", {})

        # Filter based on selector
        if parsed_selector and not all(labels.get(k) == v for k, v in parsed_selector.items()):
            logger.debug(f"Ignoring {metadata.get('name')} due to selector mismatch")
            continue

        applications.append(resource)

    return applications


@handle_exceptions
def patch_applications(applications: List[dict]) -> str:
    """
    Patch applications and convert them back to YAML.
    """
    logger.info(f"🤖 Patching {len(applications)} Argo CD Application[Sets]")

    for app in applications:
        app["metadata"]["namespace"] = "argocd"
        spec = app.get("spec", {})
        if "destination" in spec:
            spec["destination"]["name"] = "in-cluster"
            spec["destination"].pop("server", None)
        spec["project"] = "default"
        spec.pop("syncPolicy", None)
        spec["syncPolicy"] = {
            "syncOptions": ["CreateNamespace=true"]
        }

    output = "\n---\n".join([yaml.dump(app) for app in applications])
    return output


@handle_exceptions
def get_applications_as_string(directory: str, selector: Optional[str] = None) -> str:
    """
    Get applications as a string after parsing.
    """
    yaml_files = get_yaml_files(directory)
    resources = parse_yaml(yaml_files)
    applications = get_applications(resources, selector)
    
    for app in applications:
        app["metadata"]["namespace"] = "argocd"
        spec = app.get("spec", {})
        if "destination" in spec:
            spec["destination"]["name"] = "in-cluster"
            spec["destination"].pop("server", None)
        spec["project"] = "default"
        spec.pop("syncPolicy", None)  # Remove existing sync policy
        spec["syncPolicy"] = {
            "syncOptions": ["CreateNamespace=true"]
        }
        
    return yaml.dump_all([app for app in applications])


@handle_exceptions
def find_helm_resource_files(base_dir: str, path: str, helm_values: list[str], deployment_name: str) -> Optional[str]:
    """Find resource definitions in Helm values files."""
    logger.debug(f"Looking for Helm values files in {base_dir}/{path}")
    
    # Check each values file
    for value_file in helm_values:
        full_path = os.path.join(base_dir, path, value_file)
        if not os.path.exists(full_path):
            continue
            
        with open(full_path, 'r') as f:
            try:
                content = yaml.safe_load(f)
                if content and 'resources' in content:
                    logger.debug(f"Found resource definitions in {full_path}")
                    return full_path
            except yaml.YAMLError:
                logger.warning(f"Error parsing YAML in {full_path}")
                continue
    
    logger.debug(f"No Helm values files found with resource definitions")
    return None


@handle_exceptions
def find_kustomize_resource_files(base_dir: str, path: str, deployment_name: str) -> Optional[str]:
    """Find resource definitions in Kustomize files."""
    logger.debug(f"Looking for Kustomize files in {base_dir}/{path}")
    logger.debug(f"Searching for deployment: {deployment_name}")
    
    kustomization_path = os.path.join(base_dir, path, "kustomization.yaml")
    logger.debug(f"Checking kustomization path: {kustomization_path}")
    
    if not os.path.exists(kustomization_path):
        kustomization_path = os.path.join(base_dir, path, "kustomization.yml")
        logger.debug(f"First path not found, checking alternate: {kustomization_path}")
        if not os.path.exists(kustomization_path):
            logger.debug(f"No kustomization file found in {path}")
            return None
    
    try:
        with open(kustomization_path, 'r') as f:
            content = yaml.safe_load(f)
            logger.debug(f"Loaded kustomization content: {json.dumps(content, indent=2)}")
            
            if not content:
                logger.debug("Empty kustomization file")
                return None

            def check_file_for_deployment(file_path: str) -> Optional[str]:
                """Helper function to check if a file contains resource definitions."""
                if not os.path.exists(file_path):
                    logger.debug(f"File does not exist: {file_path}")
                    return None
                    
                try:
                    with open(file_path, 'r') as f:
                        file_content = yaml.safe_load(f)
                        if not file_content:
                            return None

                        # Check for resources in a deployment
                        if file_content.get('kind') == 'Deployment':
                            containers = file_content.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
                            for container in containers:
                                if 'resources' in container:
                                    logger.debug(f"Found deployment with resources in {file_path}")
                                    return file_path

                        # Check for resources in a patch
                        if 'resources' in file_content:
                            resources = file_content.get('resources', {})
                            if 'limits' in resources or 'requests' in resources:
                                logger.debug(f"Found patch with resource definitions in {file_path}")
                                return file_path
                            
                except Exception as e:
                    logger.debug(f"Error checking file {file_path}: {str(e)}")
                return None

            # Check both resources and patches in current directory
            all_files = []
            
            # Add resources
            resources = content.get('resources', [])
            logger.debug(f"Found resources in {kustomization_path}: {resources}")
            for resource in resources:
                resource_path = os.path.abspath(os.path.join(os.path.dirname(kustomization_path), resource))
                logger.debug(f"Adding resource path: {resource_path}")
                all_files.append(resource_path)
            
            # Add patches
            patches = content.get('patches', [])
            logger.debug(f"Found patches in {kustomization_path}: {patches}")
            for patch in patches:
                if isinstance(patch, dict):
                    patch_path = patch.get('path')
                    logger.debug(f"Found patch dict with path: {patch_path}")
                else:
                    patch_path = patch
                    logger.debug(f"Found patch string: {patch_path}")
                if patch_path:
                    patch_path = os.path.abspath(os.path.join(os.path.dirname(kustomization_path), patch_path))
                    logger.debug(f"Adding patch path: {patch_path}")
                    all_files.append(patch_path)
            
            # Check all files
            logger.debug(f"Checking all files: {all_files}")
            for file_path in all_files:
                if os.path.isdir(file_path):
                    # If it's a directory, recursively check it
                    logger.debug(f"Checking directory: {file_path}")
                    relative_path = os.path.relpath(file_path, base_dir)
                    result = find_kustomize_resource_files(base_dir, relative_path, deployment_name)
                    if result:
                        return result
                else:
                    result = check_file_for_deployment(file_path)
                    if result:
                        return result
            
            # Check bases if nothing found
            bases = content.get('bases', [])
            for base in bases:
                base_path = os.path.abspath(os.path.join(os.path.dirname(kustomization_path), base))
                if os.path.exists(base_path):
                    relative_path = os.path.relpath(base_path, base_dir)
                    result = find_kustomize_resource_files(base_dir, relative_path, deployment_name)
                    if result:
                        return result
    
    except yaml.YAMLError as e:
        logger.warning(f"Error parsing YAML in {kustomization_path}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error processing {kustomization_path}: {str(e)}")
        return None
    
    logger.debug(f"No Kustomize files found with resource definitions")
    return None
