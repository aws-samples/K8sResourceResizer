"""
ArgoCD client for interacting with GitOps deployments.

This module provides functionality to:
1. List ArgoCD applications in the cluster
2. Get Git repository information for applications
3. Execute ArgoCD CLI commands safely

Key features:
- Error handling for CLI operations
- JSON output parsing
- Debug logging for operations
"""

import subprocess
from logger import logger
import json
from typing import Optional, List, Dict, Any
from utils import handle_exceptions
import shutil
from pathlib import Path


@handle_exceptions
def apply_manifest(manifest_path: str) -> None:
    """Apply a Kubernetes manifest using kubectl."""
    # Validate manifest path
    manifest_path = Path(manifest_path).resolve()
    if not manifest_path.is_file():
        raise ValueError(f"Invalid manifest path: {manifest_path}")
        
    kubectl= "/usr/local/bin/kubectl"
        
    logger.info(f"Applying manifest: {manifest_path}")
    result = subprocess.run(
        [kubectl, "apply", "-f", str(manifest_path)],  # Using full path from shutil.which
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        shell=False
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Failed to apply manifest: {result.stderr}")
    
    logger.info("Successfully applied manifest")


@handle_exceptions
def get_argocd_instance() -> Optional[List[Dict[str, Any]]]:
    """Get ArgoCD applications using ArgoCD CLI."""
    argocd_bin = "/usr/local/bin/argocd"

    result = subprocess.run(
        [
            argocd_bin, "app", "list",  # Using full path
            "-o", "json"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        shell=False
    )

    if result.stdout:
        json_data = json.loads(result.stdout)
        if json_data:
            logger.debug(f"Found {len(json_data)} ArgoCD applications")
            return json_data

    logger.debug("No ArgoCD applications found")
    return None


@handle_exceptions
def get_argocd_app_git_path(argocd_app: str) -> Optional[tuple[str, str]]:
    """Use ArgoCD CLI to get the app's Git repo and path."""
    result = subprocess.run(
        [
            "argocd", "app", "get",
            argocd_app,
            "--output", "json"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False
    )

    if result.stdout:
        json_data = json.loads(result.stdout)
        repo_url = json_data["spec"]["source"]["repoURL"]
        path = json_data["spec"]["source"]["path"]
        logger.debug(f"Found Git repo {repo_url} and path {path} for ArgoCD app {argocd_app}")
        return repo_url, path

    logger.debug(f"No Git repo and path found for ArgoCD app {argocd_app}")
    return None

