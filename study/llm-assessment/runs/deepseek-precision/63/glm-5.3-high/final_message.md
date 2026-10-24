## Assessment

**Resources involved** — both declared in the same child module `modules/compute/aks` (instantiated by `module "aks_clusters"` in `aks_clusters.tf`, source `./modules/compute/aks`):

- **Source (node):** `resource "azurerm_kubernetes_cluster" "aks"` — `modules/compute/aks/aks.tf` lines 37–110. It hardcodes `role_based_access_control { azure_active_directory { managed = true, admin_group_object_ids = ... } }` (lines 93–100), i.e. AKS-managed Azure AD integration (AAD V2).
- **Target:** `resource "null_resource" "register_aks_msi_preview_feature"` — `modules/compute/aks/aks.tf` lines 175–183. Its `local-exec` provisioner (lines 157–170) runs `az feature register -n AAD-V2 --namespace Microsoft.ContainerService`, polls until the feature reports "Registered", then re-registers the `Microsoft.ContainerService` resource provider. The author comment notes it "can take around 30 mins".

**Is the ordering requirement real?** Yes. During the AAD-V2 preview era (azurerm ~2.14+, per azurerm provider PR #6530 and the Microsoft `managed-aad` docs of that time), creating an AKS cluster with managed Azure AD required the `AAD-V2` feature to be registered **and** the `Microsoft.ContainerService` RP refreshed *before* the cluster PUT — exactly the sequence this null_resource performs. On a fresh subscription where the feature isn't yet propagated, cluster creation with `managed = true` fails. Since this module unconditionally sets `managed = true`, the registration must complete before the cluster is created for the apply to succeed reliably.

**Is the dependency missing from the configuration?** Yes, verified:
- `azurerm_kubernetes_cluster.aks` has no `depends_on` block and no attribute referencing `null_resource.register_aks_msi_preview_feature` (its only references are `azurecaf_name.*`, `var.*`, `random_string.prefix`).
- The null_resource is referenced nowhere else in the repo (repo-wide grep shows only its own declaration/triggers), so it has no dependents and is a graph root alongside the cluster — Terraform will plan/apply both concurrently.
- The only `depends_on` in `aks.tf` (line 121) is inside commented-out code; the root module (`aks_clusters.tf`) passes no value derived from the null_resource and itself has no relevant `depends_on`, and root-level `depends_on` could not order child-internal resources anyway.

So both resources would be created in parallel; on an unregistered subscription the cluster can fail with a feature-not-registered error, and re-running would be needed. The proposed remedy (`depends_on = [null_resource.register_aks_msi_preview_feature]` on the AKS cluster) is the appropriate way to give Terraform the missing ordering information. All three diagnostic descriptions accurately state the gap.

Correct