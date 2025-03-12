#!/usr/bin/env bash
set -eu

# Install kind
echo "🚀 === Installing kind ==="
KIND_VERSION="v0.27.0"
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v${KIND_VERSION#v}/kind-linux-amd64
chmod +x ./kind
mv ./kind /usr/local/bin/

# Install kubectl using stable version
echo "🛠️ === Installing kubectl ==="
KUBECTL_VERSION="v1.32.2" 
echo "📦 Using kubectl version: ${KUBECTL_VERSION}"
curl -LO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/

# Install Argo CD CLI
echo "📦 === Installing Argo CD CLI ==="
ARGOCD_VERSION="v2.14.2"  
echo "📦 Using Argo CD version: ${ARGOCD_VERSION}"
curl -sSL -o /usr/local/bin/argocd \
    "https://github.com/argoproj/argo-cd/releases/download/${ARGOCD_VERSION}/argocd-linux-amd64"
chmod +x /usr/local/bin/argocd

# Verify installations
echo "🔍 === Verifying installations ==="
echo "kind version: $(kind version)"
echo "kubectl version: $(kubectl version --client -o json | jq -r '.clientVersion.gitVersion')"
echo "argocd version: $(argocd version --client | grep 'argocd: ' | cut -d ' ' -f2)"

echo "✅ === Successfully installed all tools ==="