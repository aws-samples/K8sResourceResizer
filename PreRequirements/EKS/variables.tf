variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "eks-blog-demo"
}

variable "vpc_cidr" {
  description = "VPC CIDR"
  type        = string
  default     = "10.0.0.0/16"
}

variable "cluster_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.31"
}

variable "eks_api_allowed_cidrs" {
  description = "List of CIDR blocks that can access the EKS API server endpoint"
  type        = list(string)
  default     = ["10.0.0.0/8"] # Restrict to VPC and corporate network CIDR blocks
} 