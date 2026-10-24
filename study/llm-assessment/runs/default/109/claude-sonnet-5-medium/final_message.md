I verified the Terraform configuration in `modules/infra/eks`:

- `null_resource.create_calico_installation` (in `calico.tf`) applies the Calico `Installation` CR, depending only on `apply_tigera_operator` and `kubernetes_secret.calico_image_pull`.
- `null_resource.delete_daemonset` (in `eks.tf`) runs `kubectl delete daemonset -n kube-system aws-node`, with `depends_on = [null_resource.update_kubeconfig, module.eks]` only.

There is no attribute reference or `depends_on` entry linking `delete_daemonset` to `create_calico_installation`, and no other resource chains them together (karpenter.tf's dependency on `create_calico_installation` is for a separate resource, not for `delete_daemonset`).

Operationally, deleting the `aws-node` VPC CNI DaemonSet before the Calico `Installation` CR is applied would leave the cluster with no functioning CNI during the gap between CNI removal and Calico's operator finishing its install, which is a real ordering hazard (nodes/pods lose networking, and Calico's own install might even depend on working pod networking for its controller pods). Since Terraform has no implicit way to express this via attributes on `null_resource`, an explicit `depends_on` is the correct and only way to enforce it, and it is currently missing.

All three reports accurately describe this same real gap.

Correct