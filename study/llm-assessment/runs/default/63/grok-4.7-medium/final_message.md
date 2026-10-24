The reported ordering is not required. `azurerm_kubernetes_cluster.aks` always sets managed Azure AD (`azure_active_directory.managed = true`) and does not reference `null_resource.register_aks_msi_preview_feature`, so Terraform will create them in parallel. That null resource only runs `az feature register -n AAD-V2` and re-registers `Microsoft.ContainerService`.

By this commit (19 Oct 2020) that step was no longer a creation prerequisite. AKS-managed Azure AD went GA in the 27 Jul 2020 release (public-cloud rollout finished mid-August), and Microsoft removed the AAD-V2 registration steps from the docs on 5 Aug 2020. Creating a cluster with managed AAD no longer fails if that flag has not been registered. The nearby azurerm 2.32 note that still called it a preview was stale and pointed at docs that no longer required the flag. Managed identity for AKS had also been GA since March 2020, and the identity block here is optional anyway.

The null resource is leftover registration logic, not something the cluster must wait for.

Incorrect