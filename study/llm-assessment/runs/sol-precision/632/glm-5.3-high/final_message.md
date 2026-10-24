## Assessment

### Module chain traced
`examples/analytics/spark-k8s-operator/main.tf` → `module.eks_blueprints_kubernetes_addons` (`modules/kubernetes-addons`) → `module.adot_collector_haproxy` (`modules/kubernetes-addons/adot-collector-haproxy`) → `module.helm_addon` (`modules/kubernetes-addons/helm-addon`) → `module.irsa` (`modules/irsa`).

### The two resources (`modules/irsa/main.tf`)

1. **Target** — `kubernetes_namespace_v1.irsa` (lines 1–6): created when `var.create_kubernetes_namespace && var.kubernetes_namespace != "kube-system"`. It references only `var.kubernetes_namespace`.

2. **Node** — `kubernetes_service_account_v1.irsa` (lines 8–17): created when `var.create_kubernetes_service_account`. Its `metadata.namespace` is set to `var.kubernetes_namespace` — a **plain string variable**, not a reference to the namespace resource. Its only resource reference is `aws_iam_role.irsa[0].arn` (the IAM role, which itself has no link to the namespace).

When the HAProxy ADOT collector is enabled, the wiring guarantees both resources are created: `adot-collector-haproxy/main.tf` passes `create_kubernetes_namespace = try(var.helm_config["create_namespace"], true)` (default true), `create_kubernetes_service_account = true`, and `kubernetes_namespace = "adot-collector-haproxy"` (not `kube-system`), and `helm-addon/main.tf` in turn disables Helm's own `create_namespace` (line 9), so the module's `kubernetes_namespace_v1.irsa` is the sole creator of the namespace.

### Is the ordering requirement real?

Yes. A Kubernetes ServiceAccount is a namespaced object; the Kubernetes API server rejects its creation with a 404 (`namespaces "adot-collector-haproxy" not found`) if the namespace does not yet exist, and the Kubernetes provider does not auto-create namespaces. So on a fresh cluster apply, if Terraform happens to create the service account before the namespace, the apply fails. The namespace must be created before the service account.

### Is the dependency expressed in the configuration?

No:
- **No implicit dependency**: the service account's `namespace` attribute comes from `var.kubernetes_namespace`, a plain string. Sharing a variable value does not create a resource dependency in Terraform's graph. The service account references no attribute of `kubernetes_namespace_v1.irsa` (and no output of it, directly or transitively — `outputs.tf` only exposes IAM role attributes).
- **No explicit dependency**: there is no `depends_on` on `kubernetes_service_account_v1.irsa` anywhere in `modules/irsa/main.tf`.
- **No transitive path**: `kubernetes_namespace_v1.irsa` depends on nothing but input variables, and the service account's only resource dependency is on `aws_iam_role.irsa`, which is unrelated to the namespace. The two resources are parallel roots in the dependency graph; the `helm_release` addon's `depends_on = [module.irsa]` orders the release after both, but does not order the service account after the namespace.

Therefore the reported missing dependency exists exactly as described: `kubernetes_service_account_v1.irsa` must be created only after `kubernetes_namespace_v1.irsa` when namespace creation is enabled, and Terraform currently lacks the information to enforce that ordering.

Correct