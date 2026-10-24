The report is correct, because the node group has no ordering against the policy attachments in the configuration. The only protection is indirect, and it covers just one case.

- **Node role:** `aws_eks_node_group.this` sets `node_role_arn` from `aws_iam_role.this[0].arn`. That ties it to the role but not to the role's policy attachments.
- **No explicit dependency:** the node group resource has no `depends_on`. The one `depends_on` that lists `aws_iam_role_policy_attachment.this` (at line 251 of `modules/eks-managed-node-group/main.tf`) belongs to the launch template, not the node group.
- **Indirect coverage:** `create_launch_template` defaults to `true` in `node_groups.tf`. When that is true, the node group references the launch template's name and version, so it picks up the attachment ordering through the template.
- **Where the gap shows up:** if a user sets `create_launch_template = false`, the node group has no launch template dependency. This also applies when the template comes from `launch_template_name`. In those cases nothing orders the node group after the attachments.
- **Why the ordering matters:** nodes need the worker, CNI and registry policies to join the cluster. On destroy, the policies must stay attached until EKS has removed the instances and ENIs. The AWS provider documentation for `aws_eks_node_group` recommends depending on the attachments for this reason.

The default path works by accident through the launch template, but the dependency is not expressed on the node group itself.

Correct