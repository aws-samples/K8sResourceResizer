# K8sResourceResizer

A tool that optimizes Kubernetes resource limits and requests based on historical usage patterns.

## Documentation
- [Main Project Documentation](./K8sResourceResizer/README.md) - Documentation about the K8sResourceResizer tool
- [PreRequirements Documentation](./PreRequirements/README.md) - Setup instructions and prerequisites

## Summary
K8sResourceResizer optimizes Kubernetes resource configurations through historical usage pattern analysis. It implements Prophet, Ensemble, and Time-aware approaches to set optimal CPU and memory settings. The tool integrates with Amazon Managed Prometheus (AMP) for metrics collection and supports ArgoCD workflows. Core features include business hours awareness, trend detection, and time window analysis. Users can run it locally or integrate it into CI/CD pipelines with GitHub Actions.

## Features
- Prophet, Ensemble, and Time-aware prediction strategies
- Historical analysis with configurable time windows
- Business hours awareness
- Trend detection and analysis
- Amazon Managed Prometheus (AMP) integration
- ArgoCD integration for GitOps workflows

## License
This library uses the MIT-0 License. See the LICENSE file.

