# Create a CloudWatch Log Metric Filter for unauthorized access to the Kubernetes API
resource "aws_cloudwatch_log_metric_filter" "eks_unauthorized_access" {
  name           = "${var.project_name}-eks-unauthorized-access"
  pattern        = "{ $.responseStatus.code = 401 || $.responseStatus.code = 403 }"
  log_group_name = "/aws/eks/${var.project_name}/cluster"

  metric_transformation {
    name      = "UnauthorizedAPIRequests"
    namespace = "EKS/${var.project_name}"
    value     = "1"
  }
}

# Create a CloudWatch Alarm for unauthorized access
resource "aws_cloudwatch_metric_alarm" "eks_unauthorized_access" {
  alarm_name          = "${var.project_name}-eks-unauthorized-access"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "UnauthorizedAPIRequests"
  namespace           = "EKS/${var.project_name}"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This alarm monitors for unauthorized access attempts to the Kubernetes API"
  treat_missing_data  = "notBreaching"
  
  tags = {
    Environment = "demo"
    Terraform   = "true"
    Project     = var.project_name
  }
} 