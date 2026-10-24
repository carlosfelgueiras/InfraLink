I verified the Terraform code in `modules/compute/aks/aks.tf`:

- `azurerm_kubernetes_cluster.aks` sets `role_based_access_control.azure_active_directory.managed = true` (line 97), enabling AKS-managed Azure AD integration.
- `null_resource.register_aks_msi_preview_feature` (lines 175-183) registers the `AAD-V2` preview feature on `Microsoft.ContainerService` via `az feature register` and polls until registration completes (can take ~30 minutes), then registers the provider.
- There is **no reference** from `azurerm_kubernetes_cluster.aks` to `null_resource.register_aks_msi_preview_feature` (no attribute reference, no `depends_on`), and the null_resource has no `depends_on` or reference pointing the other way either.

This is a real operational ordering requirement: the AAD-V2 preview feature must be registered on the subscription before creating an AKS cluster with managed Azure AD RBAC, or cluster creation can fail/behave inconsistently (especially on a fresh subscription where the feature isn't yet registered). Since Terraform has no dependency graph edge connecting these two resources, they would execute in parallel, so Terraform cannot guarantee the required ordering.

All three reports accurately describe this same missing dependency and the correct fix (adding `depends_on = [null_resource.register_aks_msi_preview_feature]` to the `azurerm_kubernetes_cluster.aks` resource).

Correct