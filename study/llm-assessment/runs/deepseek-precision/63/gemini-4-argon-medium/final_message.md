In `modules/compute/aks/aks.tf`, `azurerm_kubernetes_cluster.aks` configures AKS-managed Azure AD integration (`role_based_access_control.azure_active_directory.managed = true`). In the same file, `null_resource.register_aks_msi_preview_feature` uses a `local-exec` provisioner to register the required `AAD-V2` feature on the `Microsoft.ContainerService` namespace, wait for the registration to complete, and re-register the `Microsoft.ContainerService` resource provider.

However, `azurerm_kubernetes_cluster.aks` has neither an implicit attribute reference nor an explicit `depends_on` link to `null_resource.register_aks_msi_preview_feature`, allowing Terraform to attempt cluster creation before the feature registration completes.

Correct