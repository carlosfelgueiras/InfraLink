The report is correct.

In `modules/irsa/main.tf`, `kubernetes_service_account_v1.irsa` takes its namespace from `var.kubernetes_namespace`. It does not reference `kubernetes_namespace_v1.irsa`, and there is no `depends_on` on it. Terraform therefore has no way to order the two.

The namespace is created whenever `create_kubernetes_namespace` is true and the namespace is not `kube-system`. For ExternalDNS, `modules/kubernetes-addons/external-dns/locals.tf` sets that flag to `try(local.helm_config["create_namespace"], true)`. So by default the IRSA module creates the namespace.

A Kubernetes service account can only be created in a namespace that already exists. If Terraform creates the service account first, the API call fails with a "namespace not found" error.

Correct