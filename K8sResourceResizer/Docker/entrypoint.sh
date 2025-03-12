#!/usr/bin/env bash
set -eu

CLUSTER_NAME="${CLUSTER_NAME:-k8s-limits-cluster}"
# Function to wait for a specific resource to be ready
wait_for_resource() {
  local namespace="$1"
  local resource_type="$2"
  local resource_name="$3"
  local condition="$4"
  local timeout="${5:-600}"

  echo "⏳ Waiting for $resource_type/$resource_name in namespace $namespace to meet condition: $condition..."
  kubectl wait --for=condition="${condition}" --timeout="${timeout}s" "${resource_type}" "${resource_name}" -n "${namespace}" || {
    echo "❌ Timed out waiting for $resource_type/$resource_name to become ready."
    exit 1
  }
}

# Wait for the Docker daemon to be ready
echo "⏳ Waiting for Docker daemon to start..."
for i in {1..10}; do
  if docker info >/dev/null 2>&1; then
    echo "✅ Docker is ready!"
    break
  fi
  echo "🚧 Docker not ready yet, retrying... (Attempt $i/10)"
  sleep 2
  if [ "$i" -eq 10 ]; then
    echo "❌ Docker failed to start within the expected time."
    exit 1
  fi
done

KUBECONFIG_PATH="/root/.kube/config"

echo "🔧 === Creating kind cluster '${CLUSTER_NAME}' ==="

# Create a kind config file with port mappings
cat > /tmp/kind-config.yaml <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: ${CLUSTER_NAME}
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 30080  # For ArgoCD NodePort
    hostPort: 8080
    protocol: TCP
EOF

# Create the kind cluster with config
kind create cluster --config /tmp/kind-config.yaml --wait 10m

# Verify nodes are ready
echo "🔍 Checking cluster nodes..."
kubectl get nodes
echo "⏳ Waiting for nodes to be ready..."
kubectl wait --for=condition=ready nodes --all --timeout=600s
echo "✅ All nodes are ready"

# Export kubeconfig
echo "🔧 Setting up kubeconfig..."
KUBECONFIG_DIR="/root/.kube"

# Ensure kubeconfig directory exists
mkdir -p "${KUBECONFIG_DIR}"
kind export kubeconfig --name "${CLUSTER_NAME}"
echo "Kubeconfig is available at: ${KUBECONFIG_DIR}/config"
export KUBECONFIG="${KUBECONFIG_DIR}/config"

echo "🚀 === Installing Argo CD in the 'argocd' namespace ==="
# Ensure the namespace exists before applying the manifest
ARGOCD_VERSION="v2.14.2"  
echo "📦 Using Argo CD version: ${ARGOCD_VERSION}"
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml

# Wait for Argo CD server deployment to be available
wait_for_resource "argocd" "deployment" "argocd-server" "available" "600"

# Configure ArgoCD server to be accessible
echo "🔧 === Configuring ArgoCD server access ==="
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: argocd-server-external
  namespace: argocd
spec:
  type: NodePort
  ports:
  - name: https
    port: 8080
    targetPort: 8080
    nodePort: 30080
  selector:
    app.kubernetes.io/name: argocd-server
EOF

# Wait for the service to be ready
echo "⏳ Waiting for ArgoCD service..."
kubectl wait --for=condition=ready -n argocd --all pod --timeout=600s

# Additional wait for ArgoCD server to be fully ready
echo "⏳ Waiting for ArgoCD server to be fully initialized..."
wait_for_resource "argocd" "deployment" "argocd-server" "available" "300"

# Check if ArgoCD server is responding
echo "🔍 Checking ArgoCD server health..."
# Add a health check loop since service readiness doesn't guarantee API availability
for i in {1..12}; do
  if curl -k -s https://127.0.0.1:8080/healthz >/dev/null 2>&1; then
    echo "✅ ArgoCD server is healthy!"
    break
  fi
  echo "🚧 ArgoCD server not ready yet, retrying... (Attempt $i/12)"
  sleep 10
  if [ "$i" -eq 12 ]; then
    echo "❌ ArgoCD server failed to become healthy within the expected time."
    exit 1
  fi
done

# Retrieve the initial admin password
ARGOCD_PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)

echo "🎉 Argo CD deployed successfully!"
echo "🌐 Access it at: https://localhost:8080"
echo "👤 Login username: admin"
echo "🔑 Initial admin password: ${ARGOCD_PASSWORD}"

# Log in via Argo CD CLI
echo "🔐 Logging into Argo CD CLI..."
for i in {1..3}; do
  argocd login localhost:8080 \
    --username "admin" \
    --password "${ARGOCD_PASSWORD}" \
    --insecure \
    && break || {
      if [ "$i" -eq 3 ]; then
        echo "❌ Failed to log in to ArgoCD after 3 attempts"
        exit 1
      fi
      echo "⚠️ Login attempt $i failed, retrying in 5 seconds..."
      sleep 5
    }
done

echo "✅ Kubeconfig written to ${KUBECONFIG_DIR}/config"
echo "🔗 To use kubectl with this cluster, run:"
echo "    export KUBECONFIG=${KUBECONFIG_DIR}/config"
echo "🌐 Verify your cluster by running:"
echo "    kubectl cluster-info"

echo "✅ Setup complete."

# If additional arguments are provided, execute them
if [ $# -gt 0 ]; then
    echo "🚀 Executing provided command: $@"
    exec "$@"
else
    # Check if we're in local development environment (defaults to false)
    if [ "${RUN_LOCAL:-false}" = "true" ]; then
        # Keep the container running for local development
        echo "✅ Setup complete. Running in local environment, keeping container alive..."
        exec tail -f /dev/null
    else
        # Default to CI behavior - exit after completion
        echo "✅ Setup complete. Exiting..."
        exit 0
    fi
fi