The report is correct. `aws_iam_role_policy_attachment.instance_session_manager_policy` sets `role = local.aws_iam_role_instance_name`, which is a plain string built from `var.runner_iam_role_name` or `"${local.name_iam_objects}-instance"`. It has no reference to `aws_iam_role.instance`, and no `depends_on` either.

The role is created in the same module when `var.create_runner_iam_role` is true (`main.tf`, line 342). AWS rejects attaching a policy to a role that doesn't exist yet, and Terraform can't see the ordering from the name string alone. So the attachment can be attempted before the role exists, and the apply can fail.

The attachment is gated on `var.enable_runner_ssm_access` and the role on `var.create_runner_iam_role`. When the role is externally managed, there is nothing in this module to depend on. That doesn't remove the problem when the module does create the role. A conditional reference or `depends_on` would cover both cases.

Correct