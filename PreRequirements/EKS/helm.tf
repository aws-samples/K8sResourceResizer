# First create the AMP workspace
resource "aws_prometheus_workspace" "amp" {
  alias = "${var.project_name}-prometheus"

  tags = {
    Environment = "demo"
    Terraform   = "true"
  }
}

# Deploy ArgoCD
resource "helm_release" "argocd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  namespace        = "argocd"
  create_namespace = true
  version          = "5.46.7"

  values = [<<EOF
server:
  extraArgs:
    - --insecure
EOF
  ]

  depends_on = [module.eks]
}

# Deploy Prometheus
resource "helm_release" "prometheus" {
  name             = "prometheus"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  namespace        = "monitoring"
  create_namespace = true
  version          = "51.5.3"

  values = [<<EOF
prometheus:
  serviceAccount:
    name: amp-iamproxy-ingest-service-account
    annotations:
      eks.amazonaws.com/role-arn: ${aws_iam_role.prometheus.arn}

  prometheusSpec:
    remoteWrite:
      - url: https://aps-workspaces.${var.aws_region}.amazonaws.com/workspaces/${aws_prometheus_workspace.amp.id}/api/v1/remote_write
        sigv4:
          region: ${var.aws_region}
        queueConfig:
          max_samples_per_send: 1000
          max_shards: 200
          capacity: 2500

    podMonitorSelectorNilUsesHelmValues: false
    serviceMonitorSelectorNilUsesHelmValues: false

    additionalScrapeConfigs: |
      - job_name: kubernetes-pods
        honor_labels: true
        kubernetes_sd_configs:
          - role: pod
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
            action: keep
            regex: true
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
            action: replace
            target_label: __metrics_path__
            regex: (.+)
          - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
            action: replace
            regex: ([^:]+)(?::\d+)?;(\d+)
            replacement: $1:$2
            target_label: __address__
          - action: labelmap
            regex: __meta_kubernetes_pod_label_(.+)
          - action: labelmap
            regex: __meta_kubernetes_pod_annotation_(.+)
            replacement: annotation_$1
          - source_labels: [__meta_kubernetes_namespace]
            action: replace
            target_label: kubernetes_namespace
          - source_labels: [__meta_kubernetes_pod_name]
            action: replace
            target_label: kubernetes_pod_name

grafana:
  enabled: false

alertmanager:
  enabled: false
EOF
  ]

  depends_on = [module.eks, aws_iam_role_policy_attachment.prometheus]
}

# Create IAM role for Prometheus
resource "aws_iam_role" "prometheus" {
  name = "${var.project_name}-prometheus"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = module.eks.oidc_provider_arn
        }
        Condition = {
          StringEquals = {
            "${module.eks.oidc_provider}:sub" = "system:serviceaccount:monitoring:amp-iamproxy-ingest-service-account"
          }
        }
      }
    ]
  })
}

# Create IAM policy for Prometheus
resource "aws_iam_role_policy" "prometheus" {
  name = "${local.cluster_name}-prometheus"
  role = aws_iam_role.prometheus.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "aps:RemoteWrite",
          "aps:GetSeries",
          "aps:GetLabels",
          "aps:GetMetricMetadata"
        ]
        Resource = aws_prometheus_workspace.amp.arn
      }
    ]
  })
}

# Attach managed policy for Prometheus remote write
resource "aws_iam_role_policy_attachment" "prometheus" {
  role       = aws_iam_role.prometheus.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonPrometheusRemoteWriteAccess"
}
