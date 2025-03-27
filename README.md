# K8sResourceResizer

A tool for automatically optimizing Kubernetes resource limits and requests based on historical usage patterns.

## Documentation
- [Main Project Documentation](./K8sResourceResizer/README.md) - Detailed documentation about the K8sResourceResizer tool
- [PreRequirements Documentation](./PreRequirements/README.md) - Setup instructions and prerequisites

## Summary
K8sResourceResizer is an intelligent tool that automatically optimizes Kubernetes resource configurations by analyzing historical usage patterns. It uses multiple prediction strategies including Prophet, Ensemble, and Time-aware approaches to recommend optimal CPU and memory settings. The tool integrates with Amazon Managed Prometheus (AMP) for metrics collection and supports ArgoCD workflows. Key features include business hours awareness, trend detection, and support for various time windows. It can be run locally for testing or integrated into CI/CD pipelines, with GitHub Actions support provided out of the box.

## Features
- Multiple prediction strategies (Prophet, Ensemble, Time-aware, etc.)
- Support for various time windows for historical analysis
- Business hours awareness
- Trend detection and analysis
- Integration with Amazon Managed Prometheus (AMP)
- ArgoCD integration for GitOps workflows

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

