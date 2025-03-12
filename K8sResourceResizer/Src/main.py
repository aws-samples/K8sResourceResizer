"""
Main entry point for the Kubernetes Resource Optimizer.

This module orchestrates the resource optimization process by:
1. Initializing the resource optimizer with AMP credentials
2. Generating resource recommendations based on usage metrics
3. Saving recommendations to a file for tracking
4. Processing deployments to update their resource configurations
"""

import os
import sys
from pathlib import Path
import click
from dotenv import load_dotenv
from logger import setup_logger
from utils import handle_exceptions, parse_duration
from resource_optimizer import ResourceOptimizer
from manifest_updater import process_deployments
from parser import get_applications_as_string
from argocd_client import apply_manifest
import json
import secrets
from prompt_creator import build_model_prompt, python_incontext_learning
from pr_opener import clone_github_repo, invoke_bedrock_model, create_and_switch_to_branch, create_github_pull_request, commit_and_push_changes
import tempfile

# Add the Src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategy import (
    RecommendationStrategy, 
    RecommendationConfig,
    StrategyFactory
)

# Load environment variables from .env file
load_dotenv()

@click.command()
@click.option(
    "--directory",
    default="/Users/hcayada/Code/argocd-stub-repo",
    help="Directory containing YAML manifests. Default: ./manifests",
)
@click.option(
    "--output",
    default=os.path.join(os.path.dirname(os.path.dirname(__file__)), "/tmp/TEMP", "output.yaml"),
    help="Path to save modified YAML. Default: ../TEMP/output.yaml",
)
@click.option("--debug", is_flag=True, help="Enable debug mode. Default: False")
@click.option(
    "--strategy",
    type=click.Choice([s.value for s in RecommendationStrategy]),
    default=RecommendationStrategy.ENSEMBLE.value,
    help="Resource recommendation strategy to use",
)
@click.option(
    "--cpu-percentile",
    type=float,
    default=95.0,
    help="CPU percentile to use for recommendations",
)
@click.option(
    "--memory-buffer",
    type=float,
    default=1.15,
    help="Memory buffer multiplier (e.g., 1.15 for 15% buffer)",
)
@click.option(
    "--history-window",
    type=str,
    default="24h",
    help="Historical data window (e.g., 24h, 7d, 8w, 1yr). Default: 24h",
)
@handle_exceptions
def main(directory, output, debug, strategy, cpu_percentile, memory_buffer, history_window):
    """Main function to run the resource optimization process."""
    # Initialize logger with debug flag
    logger = setup_logger(debug=debug)
    logger.info("Starting resource optimization process")
    
    # Parse history window
    try:
        history_hours = parse_duration(history_window)
        logger.info(f"Using historical data window of {history_hours} hours")
    except ValueError as e:
        logger.error(f"Invalid history window format: {e}")
        sys.exit(1)
    
    # Create TEMP directory
    temp_base = tempfile.mkdtemp(prefix='k8s_resource_')
    temp_dir = os.path.join(temp_base, "TEMP")
    os.makedirs(temp_dir, exist_ok=True)

    # Create strategy configuration
    config = RecommendationConfig(
        strategy=RecommendationStrategy(strategy),
        cpu_percentile=cpu_percentile,
        memory_buffer=memory_buffer,
        business_hours_start=int(os.getenv('BUSINESS_HOURS_START', '9')),
        business_hours_end=int(os.getenv('BUSINESS_HOURS_END', '17')),
        business_days=[int(d) for d in os.getenv('BUSINESS_DAYS', '0,1,2,3,4').split(',')],
        trend_threshold=float(os.getenv('TREND_THRESHOLD', '0.1')),
        high_variance_threshold=float(os.getenv('HIGH_VARIANCE_THRESHOLD', '0.5')),
        history_window_hours=history_hours
    )
    
    # Create strategy instance
    strategy_instance = StrategyFactory.create_strategy(config)
    logger.info(f"Using {strategy} strategy for recommendations")
    
    # Get modified YAML
    modified_yaml = get_applications_as_string(directory)

    # Write to TEMP/output.yaml
    with open(output, "w") as f:
            f.write(modified_yaml)
    logger.info(f"Modified YAML saved to: {output}")

    # Apply the manifest
    logger.info(f"Applying the manifest: {output}")
    apply_manifest(output)
    
    # Initialize the resource optimizer with strategy
    optimizer = ResourceOptimizer(
        workspace_id=os.getenv('AMP_WORKSPACE_ID'),
        region=os.getenv('AWS_REGION'),
        strategy=strategy_instance
    )
    
    # Generate recommendations
    recommendations = optimizer.generate_recommendations()
    
    # Process deployments and get updated deployments
    updated_deployments = process_deployments(recommendations, directory)
    logger.info(f"Updated {len(updated_deployments)} deployments")
    
    # Prepare recommendations data structure
    logger.info("Preparing recommendations data structure")
    recommendations_data = optimizer.prepare_recommendations_to_save(recommendations, updated_deployments)
    
    # Save recommendations to file
    logger.info(f"Using TEMP directory: {temp_dir}")
    with open(os.path.join(temp_dir, "recommendations.json"), 'w') as f:
        json.dump(recommendations_data, f, indent=2)
    
    logger.info("Resource optimization process completed")

    logger.info("Starting automated process to create pull request")

    github_username = os.getenv("GITHUB_USERNAME")
    repo_name = os.getenv("GITHUB_REPOSITORY_NAME")
    github_token = os.environ.get('GIT_TOKEN')
    if not github_token:
        raise ValueError("GITHUB_TOKEN environment variable is not set")

    repo_url = f"https://{github_token}@github.com/{github_username}/{repo_name}.git"
    local_dir = os.path.join(temp_base, repo_name)
    random_number = secrets.randbelow(1000) + 1  # Generate number between 1 and 1000
    new_branch_name = f"update_resources_k8s_manifests_{random_number}"
    clone_github_repo(repo_url, local_dir)

    model_prompt = build_model_prompt(recommendations_data, repo_name)
    final_model_prompt = python_incontext_learning + model_prompt # Adding in-context learning
    region = os.getenv("AWS_REGION")
    response_for_pr_description = invoke_bedrock_model(final_model_prompt, region)

    repository_full_name = f"{github_username}/{repo_name}"
    create_and_switch_to_branch(local_dir, new_branch_name)
    commit_and_push_changes(recommendations_data, local_dir, new_branch_name, repo_url)

    
    source_branch = new_branch_name
    destination_branch = "main"
    title = "K8s manifest resource usage updates, please take a look and update with the following recommendations"

    create_github_pull_request(repository_full_name, source_branch, destination_branch, title, response_for_pr_description)
    logger.info("Automation process finished successfully")


if __name__ == "__main__":
    main()
