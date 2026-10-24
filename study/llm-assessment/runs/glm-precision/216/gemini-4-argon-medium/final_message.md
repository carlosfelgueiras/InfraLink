### Assessment

In `modules/self-managed-node-group/main.tf`, `aws_launch_template.this` configures the IAM instance profile for the self-managed nodes (`aws_iam_instance_profile.this[0].arn`) and is referenced by `aws_autoscaling_group.this` via `local.launch_template_id`.

To ensure the node IAM role has its policies attached before nodes are launched (and that policies are not detached while nodes are still running during teardown), `aws_launch_template.this` declares an explicit `depends_on`:

```hcl
  # Prevent premature access of policies by pods that
  # require permissions on create/destroy that depend on nodes
  depends_on = [
    aws_iam_role_policy_attachment.this,
  ]
```

Historically (prior to v19.0, as documented in `docs/UPGRADE-19.0.md`), `aws_iam_role_policy_attachment.this` attached both the default EKS worker/CNI policies and the user-supplied `var.iam_role_additional_policies`. When `var.iam_role_additional_policies` was split into a separate `aws_iam_role_policy_attachment.additional` resource, `depends_on` in `aws_launch_template.this` was not updated to include `aws_iam_role_policy_attachment.additional`.

Because neither `aws_launch_template.this` nor `aws_autoscaling_group.this` references or depends on `aws_iam_role_policy_attachment.additional`:
- During creation, `aws_launch_template.this` and `aws_autoscaling_group.this` can be created and launch EC2 instances before `aws_iam_role_policy_attachment.additional` finishes attaching the additional policies to `aws_iam_role.this`.
- During destruction, `aws_iam_role_policy_attachment.additional` has no dependents and will be destroyed immediately in parallel with `aws_autoscaling_group.this`, detaching policies while nodes and pods are still draining/terminating.

Therefore, the reported missing dependency from `aws_launch_template.this` to `aws_iam_role_policy_attachment.additional` is valid.

Correct