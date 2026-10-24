In `modules/irsa/main.tf` (instantiated by `module.eks_blueprints_kubernetes_addons.module.adot_collector_haproxy.module.helm_addon.module.irsa`), both the namespace and the service account are defined as follows:

```hcl
resource "kubernetes_namespace_v1" "irsa" {
  count = var.create_kubernetes_namespace && var.kubernetes_namespace != "kube-system" ? 1 : 0
  metadata {
    name = var.kubernetes_namespace
  }
}

resource "kubernetes_service_account_v1" "irsa" {
  count = var.create_kubernetes_service_account ? 1 : 0
  metadata {
    name        = var.kubernetes_service_account
    namespace   = var.kubernetes_namespace
    annotations = var.irsa_iam_policies != null ? { "eks.amazonaws.com/role-arn" : aws_iam_role.irsa[0].arn } : null
  }

  automount_service_account_token = true
}
```

In `modules/kubernetes-addons/adot-collector-haproxy/main.tf`, `irsa_config` passes `kubernetes_namespace = local.namespace` (defaulting to `"adot-collector-haproxy"`) and `create_kubernetes_namespace = try(var.helm_config["create_namespace"], true)`.

Because `kubernetes_service_account_v1.irsa` sets `metadata.namespace` directly from `var.kubernetes_namespace` instead of referencing `kubernetes_namespace_v1.irsa[0].metadata[0].name` and does not specify `depends_on = [kubernetes_namespace_v1.irsa]`, Terraform has no dependency edge between the two resources. Since a Kubernetes `ServiceAccount` is a namespaced resource, attempting to create it before the `Namespace` exists in the Kubernetes API will fail with a namespace not found error.

Correct