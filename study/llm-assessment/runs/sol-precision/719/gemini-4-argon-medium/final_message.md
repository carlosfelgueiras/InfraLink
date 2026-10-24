In `modules/kubernetes-addons/argo-workflows/main.tf`, `resource "kubernetes_namespace_v1" "this"` and `module "helm_addon"` both target the same namespace (`local.helm_config["namespace"]`, defaulting to `"argo-workflows"`), with `create_namespace = true` set in `default_helm_config`:

```hcl
module "helm_addon" {
  source = "../helm-addon"

  helm_config   = local.helm_config
  addon_context = var.addon_context
}

resource "kubernetes_namespace_v1" "this" {
  count = try(local.helm_config["create_namespace"], true) && local.helm_config["namespace"] != "kube-system" ? 1 : 0
  metadata {
    name = local.helm_config["namespace"]
  }
}
```

Because `module.helm_addon` neither references `kubernetes_namespace_v1.this` (e.g., via `kubernetes_namespace_v1.this[0].metadata[0].name`) nor declares `depends_on = [kubernetes_namespace_v1.this]` (unlike sibling add-on modules such as `argo-rollouts`, `argocd`, and `metrics-server`), Terraform can execute `helm_release.addon` and `kubernetes_namespace_v1.this` concurrently. Without ordering `module.helm_addon` after `kubernetes_namespace_v1.this`, Helm and the Kubernetes provider race on namespace creation/existence, causing an `AlreadyExists` error when Helm creates the namespace before `kubernetes_namespace_v1.this` runs.

Correct