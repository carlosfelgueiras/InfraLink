## Assessment

**Reported dependency:** `aws_eks_addon.aws_ebs_csi_driver` (node) → `module.eks_node_group_al2023` (target)

### 1. Is the dependency currently expressed in the configuration? — No

In `terraform/eks-addons.tf` (lines 44–61), the add-on's only references are:
- `cluster_name = aws_eks_cluster.cluster.name` (implicit dep on the EKS cluster)
- `service_account_role_arn = aws_iam_role.ebs_csi_controller_sa.arn` (implicit dep on the IAM role, which itself depends only on the OIDC provider)

There is no `depends_on` and no attribute reference to the node group. The module `eks_node_group_al2023` (`eks-managed-node-group-al2023.tf`, lines 47–87) also references only the cluster, launch template, node IAM role, and VPC. Both resources are downstream of `aws_eks_cluster.cluster` only, so on a fresh apply Terraform starts add-on creation **concurrently** with node-group provisioning. Both are unconditional in this configuration (`tfvars` sets `eks_addon_version_ebs_csi_driver = "v1.43.0-eksbuild.1"`, and the module has no `count`/`for_each`, with `desired_size = 3`).

### 2. Is there a concrete ordering requirement? — Yes

- **Provider behavior (verified in provider source):** `resourceAddonCreate` calls `CreateAddon` and then `waitAddonCreated`, which uses a `StateChangeConf` with `Pending: [CREATING, DEGRADED]`, `Target: [ACTIVE]`, and a default **20-minute** create timeout. The create does not succeed until EKS reports the add-on `ACTIVE`.
- **AWS semantics:** AWS documents that "Amazon EKS add-ons run on the nodes that you provision or configure for your cluster." The EBS CSI add-on deploys a controller Deployment in `kube-system` (plus a node DaemonSet). If no worker nodes exist, the controller pods stay `Pending`, EKS reports the add-on as `DEGRADED`/unhealthy, and it cannot reach `ACTIVE`.
- **Operational impact:** Managed node group provisioning (3 × m7i.4xlarge across 3 AZs, plus node bootstrap and registration) routinely takes 10–20+ minutes — the same order as the add-on's 20-minute waiter window. Concurrent installation can therefore leave the add-on stuck waiting for pod readiness and time out while workers are still provisioning, which is exactly the failure mode the report describes. This ordering requirement (workers ready before the add-on create can complete) is real, and Terraform currently has no way to enforce it.

### Conclusion

The node group must be created and have worker capacity ready before the EBS CSI driver add-on's creation can complete (reach `ACTIVE`), and the configuration expresses no implicit or explicit dependency between the two.

Correct