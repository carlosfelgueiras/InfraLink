The report is correct. The cluster sets `role_based_access_control.azure_active_directory.managed = true` (aks.tf, line 97). At this commit, that setting relies on the `AAD-V2` preview feature being registered. The `null_resource.register_aks_msi_preview_feature` resource exists to do that registration, and its own comment says it can take around 30 minutes.

Nothing connects the two. The cluster has no `depends_on`, and the `null_resource` exposes no attributes the cluster could reference. Terraform therefore has no basis to order the cluster after the registration, so it can create the cluster before registration finishes.

The cluster's node pools do reference it through `azurerm_kubernetes_cluster.aks.id`, but that only orders them after the cluster. It doesn't order the cluster after the registration.

Correct