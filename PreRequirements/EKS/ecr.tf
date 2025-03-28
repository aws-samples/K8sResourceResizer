# Create ECR repository with image scanning enabled
resource "aws_ecr_repository" "app" {
  name                 = "${var.project_name}-app"
  image_tag_mutability = "IMMUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = {
    Environment = "demo"
    Terraform   = "true"
    Project     = var.project_name
  }
}

# Create ECR repository policy to prevent deployment of images with HIGH/CRITICAL vulnerabilities
resource "aws_ecr_repository_policy" "app" {
  repository = aws_ecr_repository.app.name
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowPull"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability"
        ]
        Condition = {
          StringEquals = {
            "ecr:scan-findings-severity:CRITICAL" = "absent"
            "ecr:scan-findings-severity:HIGH"     = "absent"
          }
        }
      }
    ]
  })
} 