The report is incorrect, because no ordering from `create_calico_installation` to `delete_daemonset` is needed.

- **What the config does:** `delete_daemonset` in `eks.tf` runs `kubectl delete daemonset -n kube-system aws-node`. It depends on `module.eks` and `update_kubeconfig`. `create_calico_installation` in `calico.tf` creates the Calico `Installation` with `cni.type: Calico`.
- **Reported risk doesn't apply:** The reports claim that deleting `aws-node` first leaves the cluster with no CNI. The tigera-operator and Calico node pods run with host networking, so they don't need a pod CNI to start. Deleting `aws-node` early therefore doesn't block the Calico install.
- **Early deletion helps:** If `aws-node` is still running when Calico installs, the two CNIs compete over the CNI config directory on each node. The AWS VPC CNI's config file name sorts ahead of Calico's, so the AWS CNI would win. Deleting `aws-node` is part of making Calico the active CNI, so it doesn't need to wait for Calico.
- **Later steps are already ordered:** `karpenter.tf` already depends on `create_calico_installation`. The nodes and pods that need pod networking are created after Calico, so Terraform already sequences the work that needs a working CNI.

Incorrect