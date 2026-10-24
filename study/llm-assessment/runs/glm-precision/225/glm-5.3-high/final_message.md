Both diagnostic entries report the same source/target dependency.

The ordering requirement itself is real: EKS worker nodes need the node IAM role’s required managed policies attached before the nodes can join and operate correctly, and the Terraform AWS provider’s `aws_eks_node_group` documentation explicitly recommends depending on the role policy attachments.

However, that ordering is already expressed in this module:

- `aws_launch_template.this` explicitly depends on `aws_iam_role_policy_attachment.this`:
  - `modules/eks-managed-node-group/main.tf:287-291`
- `aws_eks_node_group.this` references `local.launch_template_id` and `local.launch_template_version` in its `launch_template` block:
  - `modules/eks-managed-node-group/main.tf:337-344`
- Those locals reference `aws_launch_template.this`:
  - `modules/eks-managed-node-group/main.tf:302-306`

So the dependency graph already contains:

`aws_iam_role_policy_attachment.this` → `aws_launch_template.this` → `aws_eks_node_group.this`

Terraform enforces transitive dependencies, so the policy attachments are created before the node group and destroyed after it. A direct `depends_on` on the node group would therefore be redundant.

Incorrect