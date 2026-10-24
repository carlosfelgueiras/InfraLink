### Assessment

The reported missing dependency from `null_resource.delete_daemonset` to `null_resource.create_calico_installation` is **incorrect**:

1. **Cluster bootstrap architecture in this module**: `module.eks` creates only the EKS control plane, which comes pre-populated with the `aws-node` DaemonSet in `kube-system`. Worker nodes in `module.self_managed_node_group` are delayed by `time_sleep.wait_300_seconds` (`300s`).
2. **Operational ordering for Calico CNI on EKS**: When replacing the AWS VPC CNI (`aws-node`) with the Calico CNI (`cni.type: Calico`), Calico's standard EKS installation procedure removes the `aws-node` DaemonSet *before* installing the Tigera operator (`tigera-operator` runs with `hostNetwork: true`) and applying the `Installation` custom resource, and before worker nodes join the cluster. Deleting `aws-node` prior to creating the `Installation` resource prevents `aws-node` and `calico-node` from competing over CNI configuration (`/etc/cni/net.d`) on nodes.
3. **API prerequisites**: `kubectl delete daemonset -n kube-system aws-node` only requires the EKS control plane and local kubeconfig to be ready, which are already enforced by `depends_on = [null_resource.update_kubeconfig, module.eks]`. It does not require `null_resource.create_calico_installation` to complete first.

Incorrect