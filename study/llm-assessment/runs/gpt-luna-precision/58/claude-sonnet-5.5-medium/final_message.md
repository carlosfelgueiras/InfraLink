The attachment's `role` is `local.aws_iam_role_instance_name`, which is a plain string local. Nothing in the attachment references `aws_iam_role.instance`. The role and the attachment are both created only when `var.create_runner_iam_role` is true, so the attachment really does need the role to exist first. Terraform has no way to know that, so it could try to attach the policy before the role is created.

I did not find any `depends_on` that covers this. The `policy_arn` references the policy, not the role. I did not confirm whether `aws_iam_role.instance` is referenced from anywhere else that would force the order. The `role` value is still a bare name, so the ordering isn't expressed.

Correct