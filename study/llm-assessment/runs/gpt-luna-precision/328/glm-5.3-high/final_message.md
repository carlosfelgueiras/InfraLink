## Assessment

**Factual check — the dependency is indeed unexpressed.** The graph in this module is:

- `aws_autoscaling_group.workers` → `aws_launch_configuration.workers` (`launch_configuration = aws_launch_configuration.workers.*.id[count.index]`)
- → `aws_iam_instance_profile.workers` (`iam_instance_profile = aws_iam_instance_profile.workers.*.id`, role from `local.default_iam_role_id`)
- → `aws_iam_role.workers`

`aws_iam_role_policy_attachment.workers_AmazonEKS_CNI_Policy` (`workers.tf:340-344`) attaches `AmazonEKS_CNI_Policy` to `aws_iam_role.workers[0]`. Since it is only a sibling of the instance profile (both depend on the role), Terraform has **no edge** — implicit or explicit — from the ASG/launch-configuration chain to this attachment. Grep confirms the policy attachments are referenced nowhere in the workers chain (only in `node_groups.tf`). So the ASG can be created (and AWS will begin launching worker instances) while the attachment is still pending.

**Is there a concrete ordering requirement?** Yes:

1. The instances this ASG launches immediately begin operating as EKS workers, and pod networking on them is initialized by the `aws-node` (aws-vpc-cni) DaemonSet using the **node instance role** (this module attaches `AmazonEKS_CNI_Policy` to the worker role precisely for this; `variables.tf:292` warns that without it "nodes will not be able to join the cluster"). If instances boot before the attachment exists, the CNI cannot initialize pod networking and the node stays NotReady/crash-loops until the policy lands.
2. The maintainers themselves treat this exact ordering as a requirement elsewhere in the same configuration: `aws_eks_cluster.this` has an explicit `depends_on` on its own role's policy attachments (`cluster.tf:41-45`), and `node_groups.tf:1-17` contains a dedicated ordering hack ("Hack to ensure ordering of resource creation… Removes race conditions") that gates managed node group creation on `workers_AmazonEKS_CNI_Policy` (and the other worker attachments) being ready — because those node groups launch instances too. The self-managed ASG path launches instances through the same worker role but lacks any equivalent ordering.

**Counterargument considered.** Neither the ASG API nor instance launch validates the role's policies, and IAM permissions are evaluated per API call, so the CNI pod would eventually succeed once the attachment completes (Kubernetes retries it). But that only means the race self-heals; it does not eliminate the real operational ordering requirement that the CNI permissions be in place when workers launch — a requirement the module enforces on the managed node group path but not here.

The report is accurate: a genuine ordering requirement exists (CNI policy attached to the worker role before the ASG launches worker instances) and it is not expressed in the configuration.

Correct