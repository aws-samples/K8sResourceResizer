# Docker Environment for K8s Resource Optimization

This Docker environment provides a complete setup for running the Kubernetes Resource Optimizer with k3d, kubectl, and Argo CD. It's designed to run without privileged mode for better security and compatibility with CI/CD platforms.

## Features

- Secure setup without privileged mode
- Pre-installed tools:
  - k3d (latest)
  - kubectl (latest stable)
  - Argo CD CLI (v2.7.3)
  - Resource Optimization tools
- Automated k3d cluster setup
- Integrated Argo CD deployment
- Support for both local development and resource optimization

## Prerequisites

- Docker installed on your host machine
- AWS credentials (for AMP access)
- Available ports:
  - 8080 (Argo CD UI)
  - 6550 (Kubernetes API)

## Building the Image

```bash
# Build with no cache
docker build --no-cache -t k8sresourceautoresizer -f Docker/Dockerfile .

# Or regular build
docker build -t k8sresourceautoresizer -f Docker/Dockerfile .
```

## Running the Container

### Local Development Mode

```bash
docker run -it \
  --network=host \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/kube:/root/.kube \
  -v $(pwd):/app \
  -e CLUSTER_NAME=eks-blog-demo \
  -e RUN_LOCAL=true \
  k8sresourceautoresizer
```

### Resource Optimization Mode Locally

```bash
docker run -it \
  --network=host \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/kube:/root/.kube \
  -v $(pwd):/app \
  -e CLUSTER_NAME=eks-blog-demo \
  -e AWS_ACCESS_KEY_ID=your-access-key \
  -e AWS_SECRET_ACCESS_KEY=your-secret-key \
  -e AWS_REGION=your-region \
  -e AMP_WORKSPACE_ID=your-workspace-id \
  -e GITHUB_REPOSITORY_NAME=your-repo-name \
  -e GITHUB_USERNAME=your-gh-username \
  -e GITHUB_TOKEN=your-gh-token \
  k8sresourceautoresizer \
  sh -c "/app/k8s-limits \
    --directory /app/manifests \
    --strategy ensemble \
    --history-window 24h \
    --cpu-percentile 95.0 \
    --memory-buffer 1.15 \
    --debug"
```

### Parameters Explained

- `--network=host`: Provides host networking for better compatibility
- `-v /var/run/docker.sock:/var/run/docker.sock`: Enables Docker-in-Docker without privileged mode
- `-p 8080:8080`: Argo CD web UI access
- `-p 6550:6550`: Kubernetes API server access
- `-v $(pwd)/kube:/root/.kube`: Persists kubeconfig
- `-v $(pwd):/app`: Mounts application directory

## Environment Variables

### Required
- `CLUSTER_NAME`: Name for the k3d cluster
- `AWS_ACCESS_KEY_ID`: AWS access key (for AMP)
- `AWS_SECRET_ACCESS_KEY`: AWS secret key (for AMP)
- `AWS_REGION`: AWS region
- `AMP_WORKSPACE_ID`: Amazon Managed Prometheus workspace ID
- `GITHUB_REPOSITORY_NAME`: Name of the GitHub Repository
- `GITHUB_USERNAME`: GitHub user name
- `GITHUB_TOKEN`: GitHub token for authentication

### Optional
- `RUN_LOCAL`: Set to "true" for development mode
- `BUSINESS_HOURS_START`: Start of business hours (default: 9)
- `BUSINESS_HOURS_END`: End of business hours (default: 17)
- `BUSINESS_DAYS`: Business days (default: 0,1,2,3,4 where 0=Monday)
- `TREND_THRESHOLD`: Threshold for trend detection
- `HIGH_VARIANCE_THRESHOLD`: Threshold for high variance detection

## Accessing Services

### Argo CD
- URL: https://localhost:8080
- Default credentials will be shown in container logs
- Login using:
  ```bash
  argocd login localhost:8080 --username admin --password <password-from-logs> --insecure
  ```

### Kubernetes
```bash
# Configure kubectl
export KUBECONFIG=$(pwd)/kube/config

# Verify connection
kubectl cluster-info
```

## Security Notes

This setup improves security by:
- Avoiding privileged mode
- Using host networking instead of privileged network access
- Mounting only necessary files and directories
- Restricting container capabilities

## Troubleshooting

1. Container startup issues:
   - Verify Docker socket permissions
   - Check port availability (8080, 6550)
   - Ensure AWS credentials are correct

2. Argo CD access issues:
   - Wait for full initialization (1-2 minutes)
   - Check container logs for password
   - Verify network connectivity

3. Resource optimization issues:
   - Validate AWS credentials
   - Check AMP workspace access
   - Verify manifest directory mounting

## Best Practices

1. Development:
   - Use `RUN_LOCAL=true` for persistent environment
   - Mount source code for live development
   - Keep kubeconfig persistent with volume mount

2. Resource Optimization:
   - Use specific time windows for analysis
   - Start with ensemble strategy
   - Adjust thresholds based on application patterns
   - Monitor optimization results

## Cleanup

```bash
# Stop container
docker stop $(docker ps -q --filter ancestor=k8sresourceautoresizer)

# Remove container
docker rm $(docker ps -aq --filter ancestor=k8sresourceautoresizer)

# Remove image (optional)
docker rmi k8sresourceautoresizer
```
## Security Notes

### Docker Socket Mounting vs Privileged Mode

This setup uses Docker socket mounting (`-v /var/run/docker.sock:/var/run/docker.sock`) instead of privileged mode (`--privileged`) for enhanced security:

1. **Reduced Attack Surface**: Only exposes Docker API functionality instead of full host access
2. **Principle of Least Privilege**: Container only gets the permissions it needs
3. **Better Security Practices**: Aligns with container security best practices
4. **Maintained Functionality**: Preserves required container management capabilities

### Best Practices

1. Use non-root user inside container when possible
2. Keep base image updated
3. Scan container images for vulnerabilities
4. Use specific versions for dependencies
5. Implement proper secret management

## Troubleshooting

1. **Docker Socket Permission Issues**:
   ```bash
   # Add current user to docker group
   sudo usermod -aG docker $USER
   # Restart Docker service
   sudo systemctl restart docker
   ```

2. **Network Access Issues**:
   - Ensure host network mode is enabled
   - Check firewall rules for required ports
   - Verify AWS credentials have necessary permissions

3. **Volume Mount Issues**:
   - Ensure paths exist on host
   - Check file permissions
   - Use absolute paths when needed

For more detailed troubleshooting, check the logs with:
```bash
docker logs <container_id>
``` 