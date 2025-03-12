# EKS Auto Mode Cluster with ArgoCD and Amazon Managed Prometheus

This Terraform configuration creates an EKS cluster using Auto Mode with ArgoCD and Amazon Managed Prometheus (AMP) integration.

## Infrastructure Components

### VPC (`vpc.tf`)
- Creates a VPC with public and private subnets across 3 availability zones
- NAT Gateway for private subnet internet access
- Proper tagging for EKS use
- CIDR: 10.0.0.0/16
- **VPC Flow Logs** enabled to capture network traffic information:
  - Logs stored in CloudWatch Logs (7-day retention)
  - Captures all traffic (ingress and egress)
  - 1-minute aggregation interval
  - Helps troubleshoot network connectivity issues

### EKS Cluster (`eks.tf`)
- EKS cluster with both private and public endpoints
- Public endpoint restricted to allowed CIDR blocks
- Control plane logging enabled for audit, API, authenticator, controller manager, and scheduler
- KMS encryption for Kubernetes secrets
- Security groups configured to only allow inbound traffic on port 443
- Latest stable Kubernetes version (1.31)
- OIDC provider for IAM roles for service accounts (IRSA)

### ArgoCD (`helm.tf`)
- Deployed via Helm in `argocd` namespace
- Configured with admin access
- Credentials:
  - Username: admin
  - Password: admin
- Accessible via port-forward

### Amazon Managed Prometheus (`helm.tf`)
- AMP workspace creation
- Prometheus deployment configured to write to AMP
- IAM roles and policies for Prometheus
- Auto-discovery of pod metrics
- Accessible via AWS Console and port-forward

## Prerequisites

- AWS CLI configured
- Terraform >= 1.0
- kubectl
- helm

## File Structure

```
.
├── eks.tf          # EKS cluster configuration
├── helm.tf         # ArgoCD and Prometheus deployments
├── variables.tf    # Variable definitions
├── vpc.tf          # VPC and networking
├── providers.tf    # AWS and Kubernetes providers
└── outputs.tf      # Cluster outputs
```

### File Descriptions

#### `variables.tf`
```hcl
aws_region       # AWS region (default: eu-central-1)
project_name     # Project name (default: eks-blog-demo)
vpc_cidr         # VPC CIDR (default: 10.0.0.0/16)
cluster_version  # EKS version (default: 1.31)
```

#### `vpc.tf`
- Creates VPC using AWS VPC module
- Sets up public, private, and intra subnets
- Configures NAT Gateway and routing

#### `eks.tf`
- Creates EKS cluster using AWS EKS module
- Configures node groups and IAM roles
- Sets up OIDC provider for IRSA

#### `helm.tf`
- Deploys ArgoCD
- Creates AMP workspace
- Deploys Prometheus with AMP integration
- Sets up IAM roles for Prometheus

## Usage

1. Initialize Terraform: 
```bash
terraform init
```

2. Review the changes:
```bash
terraform plan
```

3. Apply the changes:
```bash
terraform apply
```

4. Configure kubectl:
```bash
aws eks update-kubeconfig --region eu-central-1 --name eks-blog-demo
```

## Accessing Services

### ArgoCD
```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Access via: http://localhost:8080
# Username: admin
# Password: admin
```

### Prometheus
```bash
kubectl port-forward svc/prometheus-operated -n monitoring 9090:9090
# Access via: http://localhost:9090
```

### Amazon Managed Prometheus
Access through AWS Console:
1. Go to Amazon Managed Service for Prometheus
2. Select workspace: eks-blog-demo-prometheus

## Adding Application Metrics

Add these annotations to your pods for Prometheus scraping:
```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "metrics-port"
  prometheus.io/path: "/metrics"
```

## Cleanup

To destroy all resources:
```bash
terraform destroy
```

## Troubleshooting

### Common Issues

1. IRSA not working:
```bash
kubectl describe serviceaccount amp-iamproxy-ingest-service-account -n monitoring
```

2. Prometheus not collecting metrics:
```bash
kubectl logs -n monitoring prometheus-prometheus-kube-prometheus-prometheus-0
```

3. ArgoCD not accessible:
```bash
kubectl get pods -n argocd
kubectl describe svc argocd-server -n argocd
```

## Security Notes

- EKS cluster endpoint is public but requires AWS IAM auth
- ArgoCD uses basic auth (change password in production)
- Prometheus uses AWS SigV4 for AMP authentication
- All pod metrics are collected and stored in AMP

## ArgoCD Admin Password

ArgoCD will automatically generate a random admin password. To retrieve this password, use the following command:

```bash
kubectl -n argocd get secret argocd-initial-admin-password -o jsonpath="{.data.password}" | base64 -d
```

This command will:
1. Access the secret where ArgoCD stores the initial admin password
2. Extract the password field
3. Decode it from base64

### Changing the ArgoCD Password

After first login, it's recommended to change the admin password:

```bash
# Login to ArgoCD
argocd login localhost:8080 --username admin --password $(kubectl -n argocd get secret argocd-initial-admin-password -o jsonpath="{.data.password}" | base64 -d)

# Update password
argocd account update-password --current-password $(kubectl -n argocd get secret argocd-initial-admin-password -o jsonpath="{.data.password}" | base64 -d) --new-password your-new-secure-password
```

This approach is more secure than hardcoding passwords in your Terraform configuration files.

### Security Features
- **KMS Encryption**: Envelope encryption for Kubernetes secrets
- **Private Endpoint**: Secure access from within VPC
- **CIDR Restrictions**: API server only accessible from allowed networks
- **Control Plane Logs**: All logs streamed to CloudWatch
- **CloudWatch Alarms**: Alerts for unauthorized API access attempts
- **VPC Flow Logs**: Network traffic visibility and troubleshooting
- **ECR Scanning**: Automatic vulnerability scanning of container images
- **Security Policies**: Block deployment of images with HIGH/CRITICAL vulnerabilities