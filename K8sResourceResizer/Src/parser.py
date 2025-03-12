import os
import yaml
from loguru import logger
from typing import List, Optional, Dict


class K8sResource:
    def __init__(self, file_name: str, yaml_content: dict):
        self.file_name = file_name
        self.yaml_content = yaml_content


class Application:
    def __init__(self, file_name: str, yaml_content: dict, kind: str):
        self.file_name = file_name
        self.yaml_content = yaml_content
        self.kind = kind


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


def parse_yaml(files: List[str]) -> List[K8sResource]:
    """
    Parse YAML files into K8sResource objects.
    """
    resources = []
    for file_path in files:
        logger.debug(f"Processing file: {file_path}")
        with open(file_path, "r") as f:
            try:
                documents = list(yaml.safe_load_all(f))
                for doc in documents:
                    if doc is not None:
                        resources.append(K8sResource(file_path, doc))
            except yaml.YAMLError as e:
                logger.warning(f"Failed to parse file {file_path}: {e}")
    return resources


def parse_selector(selector: Optional[str]) -> Dict[str, str]:
    """
    Parse a text-based selector in the format 'key=value'.
    """
    if not selector:
        return {}

    try:
        key, value = selector.split("=")
        return {key.strip(): value.strip()}
    except ValueError:
        logger.error(f"Invalid selector format: {selector}. Expected format: 'key=value'.")
        return {}


def get_applications(resources: List[K8sResource], selector: Optional[str] = None) -> List[Application]:
    """
    Filter and return applications from K8s resources based on the selector.
    """
    applications = []
    parsed_selector = parse_selector(selector)

    for resource in resources:
        kind = resource.yaml_content.get("kind")
        if kind not in ["Application", "ApplicationSet"]:
            continue

        metadata = resource.yaml_content.get("metadata", {})
        labels = metadata.get("labels", {})

        # Filter based on selector
        if parsed_selector and not all(labels.get(k) == v for k, v in parsed_selector.items()):
            logger.debug(f"Ignoring {metadata.get('name')} due to selector mismatch")
            continue

        applications.append(Application(resource.file_name, resource.yaml_content, kind))

    return applications


def patch_applications(applications: List[Application]) -> str:
    """
    Patch applications and convert them back to YAML.
    """
    logger.info(f"🤖 Patching {len(applications)} Argo CD Application[Sets]")

    for app in applications:
        app.yaml_content["metadata"]["namespace"] = "argocd"
        spec = app.yaml_content.get("spec", {})
        if "destination" in spec:
            spec["destination"]["name"] = "in-cluster"
            spec["destination"].pop("server", None)
        spec["project"] = "default"
        spec.pop("syncPolicy", None)

    output = "\n---\n".join([yaml.dump(app.yaml_content) for app in applications])
    return output


def get_applications_as_string(directory: str, selector: Optional[str] = None) -> str:
    """
    Get applications as a string after parsing and patching.
    """
    yaml_files = get_yaml_files(directory)
    resources = parse_yaml(yaml_files)
    applications = get_applications(resources, selector)
    return patch_applications(applications)
