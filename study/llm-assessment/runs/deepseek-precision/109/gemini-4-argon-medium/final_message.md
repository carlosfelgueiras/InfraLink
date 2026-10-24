The diagnostic report claims that `:resource.null_resource.delete_daemonset` must depend on `:resource.null_resource.create_calico_installation` so that the default AWS VPC CNI (`aws-node` DaemonSet) is only deleted after the Calico `Installation` custom resource has been created.

Inspecting the Terraform configuration in `modules/infra/eks` and the operational semantics of installing Calico CNI on Amazon EKS shows that this claim is **incorrect**:

1. **Cluster and Node Provisioning Flow**:
   - `module.eks` (`eks.tf`) provisions the EKS control plane without any initial worker node groups.
   - `module.self_managed_node_group` (`nodes.tf`) provisions the worker nodes, and it explicitly depends on `time_sleep.wait_300_seconds` (which waits 300 seconds after `module.eks` completes).
   - Meanwhile, `null_resource.update_kubeconfig`, `null_resource.delete_daemonset`, and `null_resource.apply_tigera_operator` run immediately after `module.eks` while there are no worker nodes in the cluster.

2. **Standard Calico CNI on EKS Installation Procedure**:
   - According to the official Project Calico documentation for installing Calico networking (`spec.cni.type: Calico`) on EKS:
     1. Create the EKS cluster without nodes.
     2. Delete the `aws-node` DaemonSet (`kubectl delete daemonset -n kube-system aws-node`) to disable AWS VPC networking.
     3. Install the Tigera Operator (`tigera-operator.yaml`).
     4. Create the Calico `Installation` resource (`null_resource.create_calico_installation`).
     5. Add worker nodes to the cluster.
   - Because `tigera-operator` itself runs with `hostNetwork: true`, it does not require a CNI plugin (`aws-node` or Calico) to start on a node and reconcile the `Installation` custom resource into the `calico-node` DaemonSet.
   - Furthermore, both `null_resource.delete_daemonset` and `null_resource.create_calico_installation` simply modify Kubernetes API objects on the EKS control plane before worker nodes join; deleting `aws-node` does not require the `Installation` custom resource to exist first (in fact, removing `aws-node` before or alongside installing Calico prevents `aws-node` and `calico-node` from competing to write CNI configurations on nodes).

Therefore, `null_resource.delete_daemonset` does not require `null_resource.create_calico_installation` to be created first.

Incorrect