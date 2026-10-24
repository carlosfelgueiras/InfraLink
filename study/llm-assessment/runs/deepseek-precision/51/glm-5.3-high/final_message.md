## Assessment

**Reported missing dependency:** `kubernetes_storage_class_v1.efs` → `module.eks_blueprints_kubernetes_addons` (EFS CSI driver addon)

### Configuration facts

In `examples/stateful/main.tf`:

- `kubernetes_storage_class_v1.efs` (line 213) sets `storage_provisioner = "efs.csi.aws.com"` as a **literal string** and `parameters.fileSystemId = module.efs.id`. Its only resource-level dependency is on `module.efs`; it has no `depends_on` and no reference to `module.eks_blueprints_kubernetes_addons` — so the reported edge is indeed absent. (Its provider-level prerequisite — a reachable, authenticated API server — is already satisfied via the `kubernetes` provider config referencing `module.eks_blueprints` / `data.aws_eks_cluster_auth`.)
- `module.eks_blueprints_kubernetes_addons` enables `enable_aws_efs_csi_driver = true`, which deploys the `aws-efs-csi-driver` Helm chart (v2.2.9) into `kube-system` via a `helm_release`.

### Is there a concrete ordering requirement?

No. The report's premise — that the provisioner only "works" once the driver is installed — is true, but it is irrelevant to **creation of the StorageClass**:

1. **A StorageClass is inert API metadata.** The Kubernetes API server does not validate that a `provisioner` string corresponds to a running or registered provisioner, and the `aws-efs-csi-driver` chart installs no admission webhook that touches StorageClass creation. The resource will be created successfully whether the driver is installed, installing, or absent — there is no apply-time failure mode.
2. **The driver only matters at PVC-provisioning time**, when the driver's controller watches for PVCs referencing the class. This example creates no PVCs, StatefulSets, or workloads that consume the `efs` class; any consumer is external and post-apply, by which time the whole apply (including the addon) has completed. A dependency would at best belong on such a hypothetical consumer resource, not on the StorageClass itself.
3. **Ordering has no effect on the end state.** Whether the class is created before, concurrently with, or after the driver, the resulting cluster is identical — the driver does not read or require pre-existing state from the StorageClass.
4. This is consistent with the repo's own pattern: the sibling `kubernetes_storage_class_v1.gp3` (provisioner `ebs.csi.aws.com`, whose driver is likewise installed by the same addons module) also declares no such dependency.

The report accurately observes that no dependency edge exists, but the claimed necessity ("should depend on the driver that implements the provisioner") does not hold: relatedness is not an ordering requirement, and `depends_on` here would encode nothing that affects correctness of the apply.

Incorrect