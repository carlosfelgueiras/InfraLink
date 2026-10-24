The `kubectl_manifest.cluster_pca_issuer` resource has no `depends_on` block, and nothing in it references the addons module. Its only references are `module.eks_blueprints.eks_cluster_id` and the CA ARN. The AWS PCA issuer addon, which installs the `AWSPCAClusterIssuer` CRD, is deployed by `module.eks_blueprints_kubernetes_addons`. Without that ordering, a fresh apply could try to create the custom resource before its CRD exists, and fail with an unknown resource kind.

I didn't open the addons module to confirm that it installs the CRD. I'm relying on its role in this example and on the later `depends_on` at lines 187–189, which already lists both the addons module and this resource.

Correct