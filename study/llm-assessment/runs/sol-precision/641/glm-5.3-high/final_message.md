**Assessment: Correct**

In `modules/kubernetes-addons/opentelemetry-operator/main.tf`, `aws_eks_addon.adot` currently waits for:

- `module.cert_manager` via `depends_on`
- `kubernetes_role_v1.adot` and `kubernetes_cluster_role_v1.adot` implicitly through the `RoleVersion` and `ClusterRoleVersion` tag values

It does **not** reference or depend on `kubernetes_role_binding_v1.adot`.

That binding is operationally significant: it binds the Kubernetes user `eks:addon-manager` to the namespaced ADOT prerequisite Role. A Kubernetes `Role` by itself grants no permissions to that user; the `RoleBinding` is what supplies the authorization. AWS’s ADOT EKS add-on prerequisite manifest includes this RoleBinding, and those permissions must be present before the managed add-on can install its Kubernetes resources.

Because `aws_eks_addon.adot` can otherwise be created before the RoleBinding exists, the ordering requirement is real and is not currently expressed in the Terraform configuration.

Correct