I've inspected the configuration. Here's my assessment:

## Configuration facts

**`null_resource.delete_daemonset`** (`modules/infra/eks/eks.tf:79-87`):
- Runs `kubectl delete daemonset -n kube-system aws-node` — removes the AWS VPC CNI DaemonSet.
- `depends_on = [null_resource.update_kubeconfig, module.eks]` — its entire dependency closure is the kubeconfig update and the EKS module.

**`null_resource.create_calico_installation`** (`modules/infra/eks/calico.tf:44-67`):
- Applies the Tigera `Installation` CR (`cni.type: Calico`, `kubernetesProvider: EKS`) via `kubectl create -f -`, which is what causes the Tigera operator to deploy Calico as the pod-network CNI.
- Depends on `null_resource.apply_tigera_operator` and `kubernetes_secret.calico_image_pull` (which in turn depend on `null_resource.update_kubeconfig`).

**Dependency overlap:** Both chains share the root `null_resource.update_kubeconfig` / `module.eks`, but sibling branches of a shared dependency have no enforced ordering in Terraform. Nothing in `delete_daemonset`'s graph references `create_calico_installation` or anything downstream of it, so Terraform is free to delete `aws-node` before (or concurrently with) the Calico `Installation` being created.

## Operational requirement

This is the standard, documented CNI-swap procedure for EKS (Calico's own installation guide): install the Tigera operator and `Installation` (Calico), and only then delete the `aws-node` DaemonSet. Deleting `aws-node` tears down the VPC CNI's IPAM on every node — if Calico hasn't been installed yet, new pods scheduled in the interim have no functional CNI and fail to get pod networking. There is therefore a concrete ordering requirement from `create_calico_installation` → `delete_daemonset`.

The module's own intent confirms this: `module.karpenter` is explicitly ordered after `null_resource.create_calico_installation` (`karpenter.tf:22-28`), showing the authors expect Calico in place before workload-affecting steps run — yet `delete_daemonset` was left unordered relative to it.

Since `null_resource` has no attribute that could serve as an implicit reference, and no `depends_on` link exists, Terraform currently cannot enforce this ordering.

Correct