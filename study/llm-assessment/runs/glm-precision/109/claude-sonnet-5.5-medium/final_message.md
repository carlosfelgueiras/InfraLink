The report is correct, since nothing in the configuration orders the two resources.

- `null_resource.delete_daemonset` (`eks.tf`) depends only on `null_resource.update_kubeconfig` and `module.eks`.
- `null_resource.create_calico_installation` (`calico.tf`) depends only on `null_resource.apply_tigera_operator`, which in turn depends on `update_kubeconfig`.
- Neither resource references the other, so Terraform can run them in parallel. Both are local-exec `kubectl` commands, so no attribute reference could create the ordering.

The ordering matters in practice. The Installation tells the Tigera operator to deploy Calico as the CNI (`cni.type: Calico`), which replaces the AWS VPC CNI. If `kubectl delete daemonset aws-node` runs first, the cluster has no CNI until Calico is up. Pods scheduled in that gap can fail to get networking. Deleting `aws-node` only after the Installation is applied is the safe order, and a `depends_on` is the only way to express it here.

Correct