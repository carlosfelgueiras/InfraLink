### Assessment

In `examples/tls-with-aws-pca-issuer/main.tf`, `resource "kubectl_manifest" "cluster_pca_issuer"` (lines 134–148) creates a Kubernetes custom resource of kind `AWSPCAClusterIssuer` (`apiVersion: awspca.cert-manager.io/v1beta1`):

```hcl
resource "kubectl_manifest" "cluster_pca_issuer" {
  yaml_body = yamlencode({
    apiVersion = "awspca.cert-manager.io/v1beta1"
    kind       = "AWSPCAClusterIssuer"

    metadata = {
      name = module.eks_blueprints.eks_cluster_id
    }

    spec = {
      arn = aws_acmpca_certificate_authority.example.arn
      region : local.region
    }
  })
}
```

The `AWSPCAClusterIssuer` CustomResourceDefinition (CRD) is installed into the EKS cluster by the `aws-privateca-issuer` Helm chart managed inside `module.eks_blueprints_kubernetes_addons` (configured with `enable_aws_privateca_issuer = true` on line 82).

Currently, `kubectl_manifest.cluster_pca_issuer` only has implicit dependencies on `module.eks_blueprints` (via `metadata.name` and the `kubectl` provider configuration) and `aws_acmpca_certificate_authority.example` (via `spec.arn`). Unlike `kubectl_manifest.example_pca_certificate` (lines 187–190), it has neither an implicit reference nor an explicit `depends_on` pointing to `module.eks_blueprints_kubernetes_addons`. Consequently, Terraform can attempt to apply `kubectl_manifest.cluster_pca_issuer` before `module.eks_blueprints_kubernetes_addons` has installed the `AWSPCAClusterIssuer` CRD.

Correct