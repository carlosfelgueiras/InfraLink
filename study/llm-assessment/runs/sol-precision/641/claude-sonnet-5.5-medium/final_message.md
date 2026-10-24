The report is correct.

- **What the config expresses today:** `aws_eks_addon.adot` has implicit dependencies on `kubernetes_role_v1.adot` and `kubernetes_cluster_role_v1.adot`. These come from the `RoleVersion` and `ClusterRoleVersion` tags in `modules/kubernetes-addons/opentelemetry-operator/main.tf`. Its only `depends_on` is `module.cert_manager`.
- **What is missing:** nothing links the add-on to `kubernetes_role_binding_v1.adot`. Terraform can create the add-on before the binding exists. The same gap applies to `kubernetes_cluster_role_binding_v1.adot`, which is only mentioned here as a related case.
- **Why the ordering matters:** the role is only a set of permissions. It grants nothing to `eks:addon-manager` until a binding attaches it. The binding's subject is the user named by `local.eks_addon_role_name`, and its `role_ref` points at the role.
- **Effect on the add-on:** EKS needs those permissions when it installs or removes the managed ADOT resources. Without the binding in place first, the install can fail or race.

Correct