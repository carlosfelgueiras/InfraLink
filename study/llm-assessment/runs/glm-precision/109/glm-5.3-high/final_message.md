## Assessment

**Configuration (as found):**

- `modules/infra/eks/eks.tf:79` — `null_resource.delete_daemonset` runs `kubectl delete daemonset -n kube-system aws-node` and depends only on `null_resource.update_kubeconfig` and `module.eks`.
- `modules/infra/eks/calico.tf:11` — `null_resource.create_calico_installation` applies the Calico `Installation` CR (`kubernetesProvider: EKS`, `cni: Calico`) and depends on `null_resource.apply_tigera_operator` → `null_resource.update_kubeconfig`.

The graph-structure claim is accurate: the two null_resources share only `update_kubeconfig` as a common ancestor, so Terraform may execute them concurrently. The question is whether a **target → node ordering requirement** actually exists.

**Why the claimed ordering requirement does not hold:**

1. **Calico's documented EKS procedure orders the steps the other way.** The official docs for v3.29 (the version pinned in this module's manifest URLs, `v3.29.1`) and the latest version both prescribe, for "Install EKS with Calico networking": (a) create the cluster, (b) *delete the `aws-node` daemonset* — "Since this cluster will use Calico for networking, you must delete the `aws-node` daemon set to disable AWS VPC networking for pods" — and only then (c) install the Tigera operator and (d) apply the `Installation` CR. The report's core factual claim ("Calico's standard EKS install order requires deleting aws-node only after the Installation is applied") is the opposite of what the vendor documents. Delete-first is intentional: it removes the AWS VPC CNI so Calico cleanly takes over, avoiding two competing CNIs on each node (calico-node is `hostNetwork`, so it can start and provide CNI on a node with no other CNI running).

2. **The proposed dependency wouldn't deliver the claimed benefit.** `kubectl create -f` of the `Installation` CR is asynchronous — it merely registers the CR; the Tigera operator still needs tens of seconds to minutes to roll out a ready `calico-node` DaemonSet. So even with `delete_daemonset` ordered after `create_calico_installation`, any pod scheduled during the operator's rollout window would still lack pod networking. The gap between "aws-node removed" and "Calico actually providing CNI" exists under either command ordering; a `depends_on` between the two kubectl invocations does not close it.

3. **Neither command requires the other.** `kubectl delete daemonset aws-node` and `kubectl create -f <Installation>` are independent API-server operations; each succeeds regardless of whether the other has run. Their end state is identical in either order (transient timing differences only, and existing pods keep their already-attached ENIs across the daemonset deletion).

There is no concrete ordering requirement that `create_calico_installation` must exist before `delete_daemonset` can be correctly executed — indeed the vendor's standard procedure prescribes the reverse order.

Incorrect