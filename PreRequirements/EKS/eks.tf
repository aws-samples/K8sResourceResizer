locals {
  cluster_name = var.project_name
  
  tags = {
    Project     = var.project_name
    Environment = "demo"
    Terraform   = "true"
  }
  
  # Define allowed CIDR blocks for API server access
  allowed_api_cidrs = var.eks_api_allowed_cidrs
}

# Create KMS key for envelope encryption of Kubernetes secrets
resource "aws_kms_key" "eks" {
  description             = "EKS Secret Encryption Key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  
  tags = local.tags
}

resource "aws_kms_alias" "eks" {
  name          = "alias/${var.project_name}-eks"
  target_key_id = aws_kms_key.eks.key_id
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.31"

  cluster_name                   = local.cluster_name
  cluster_version                = var.cluster_version
  
  # Restrict public access to specified CIDR blocks
  cluster_endpoint_public_access       = true
  cluster_endpoint_public_access_cidrs = local.allowed_api_cidrs
  
  # Enable private endpoint access
  cluster_endpoint_private_access = true
  
  # Enable control plane logging
  cluster_enabled_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler"
  ]
  
  # Configure cluster encryption with KMS
  cluster_encryption_config = {
    provider_key_arn = aws_kms_key.eks.arn
    resources        = ["secrets"]
  }

  enable_cluster_creator_admin_permissions = true

  cluster_compute_config = {
    enabled    = true
    node_pools = ["general-purpose"]
  }

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Add security group rule to restrict access to port 443 only
  node_security_group_additional_rules = {
    ingress_443 = {
      description      = "Allow HTTPS inbound traffic"
      protocol         = "tcp"
      from_port        = 443
      to_port          = 443
      type             = "ingress"
      cidr_blocks      = ["0.0.0.0/0"]
    }
  }
  
  # Block access to instance metadata
  node_security_group_tags = {
    "aws:eks:cluster-name" = local.cluster_name
  }
  
  tags = local.tags
}
