The report is correct. The attachment sets `role = local.aws_iam_role_instance_name`, which is a plain string built from `var.runner_iam_role_name` or `"${local.name_iam_objects}-instance"`. It does not reference `aws_iam_role.instance`, and the resource has no `depends_on`.

When `var.create_runner_iam_role` is true, the module creates `aws_iam_role.instance` with that same name. In that case, `aws_iam_role_policy_attachment` must run after the role exists, because `AttachRolePolicy` fails with NoSuchEntity if the role is missing. Terraform has no information linking the two resources, so it can apply the attachment first.

One condition applies. `aws_iam_role_policy_attachment.instance_session_manager_policy` is gated only by `enable_runner_ssm_access`, so the ordering gap matters only when the module also creates the role. It does in the default case. If the user supplies an existing role, no ordering is needed.

Correct