## Assessment

I inspected `modules/eks-managed-node-group/main.tf` (the module instantiated by `module "eks_managed_node_group"` in `node_groups.tf`) at commit `ef22c798`.

**Current dependency structure of the node (`aws_eks_node_group.this`, lines 269–348):**
- `node_role_arn = var.create_iam_role ? aws_iam_role.this[0].arn : var.iam_role_arn` → implicit dependency on `aws_iam_role.this` **only**
- No `depends_on` on the node group resource
- No attribute reference to `aws_iam_role_policy_attachment.this` anywhere in its arguments (its only other module-managed reference is to `aws_launch_template.this` via `local.launch_template_name`/`local.launch_template_version`, which wrap `try(aws_launch_template.this[0].name, ...)`)

**The only existing path to the target (`aws_iam_role_policy_attachment.this`) is the launch template's `depends_on` (lines 251–254), which is conditional:**
- `aws_launch_template.this` has `count = var.create && var.create_launch_template ? 1 : 0`. When `create_launch_template = false` (a first-class supported configuration — the node group then uses EKS's default launch template or a user-supplied external one), the launch template produces no instances, so Terraform materializes no ordering edge from the node group to the policy attachments. I confirmed in Terraform's apply-graph implementation (`graph_builder_apply.go`, `node_resource_apply.go`) that only instance nodes carry body/`depends_on` references and that the resource-level expansion node carries only `count`/`for_each` references — a `count = 0` resource does not propagate its `depends_on` to dependents.
- Even in the module-created launch template case, the ordering exists only incidentally through that chain, not on the node group itself, and disappears as soon as the module stops creating the launch template.

**The ordering requirement is real and documented.** The AWS provider documentation for `aws_eks_node_group` (v4.x, contemporary with this commit) explicitly prescribes `depends_on` on the node group listing the worker node/CNI/ECR policy attachments:

> *"Ensure that IAM Role permissions are created before and deleted after EKS Node Group handling. Otherwise, EKS will not be able to properly delete EC2 Instances and Elastic Network Interfaces."*

Concretely:
- **Create:** both the node group and the policy attachments depend only on `aws_iam_role.this`, so Terraform may create them concurrently — EKS immediately launches instances that assume a role that is still permissionless, so nodes cannot pull images from ECR or assign pod IPs and fail to register.
- **Destroy:** the node group deletion and the policy detachments are mutually unordered (both are only ordered against the IAM role, and the role has `force_detach_policies = true`), so permissions can be stripped while EKS is still terminating instances — the documented failure where EKS cannot delete the instances/ENIs.

The report's reasoning is accurate: the node group orders only against the bare role; the launch template's `depends_on` covers only the module-created launch template case; and the provider documentation recommends this exact dependency for exactly these failure modes. The required ordering (policy attachments ready before node group creation, node group deletion before detachment) is not expressed on `aws_eks_node_group.through` either an attribute reference or `depends_on`, and Terraform lacks the information needed to enforce it in supported configurations.

Correct