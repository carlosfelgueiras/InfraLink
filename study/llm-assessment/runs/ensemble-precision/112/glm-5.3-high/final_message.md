The report is correct.

`aws_iam_role_policy_attachment.instance_session_manager_policy` sets:

```hcl
role       = local.aws_iam_role_instance_name
policy_arn = aws_iam_policy.instance_session_manager_policy[0].arn
```

The `role` value is only a plain local string. It does not reference `aws_iam_role.instance`, and the resource has no `depends_on` declaration. Its only implicit dependency is on the IAM policy.

When `var.create_runner_iam_role` and `var.enable_runner_ssm_access` are both true, the target IAM role is module-managed and must exist before the attachment can be created. Without a Terraform dependency edge, the attachment can be attempted before the role exists, causing an AWS `NoSuchEntity`-style failure. The missing edge also means Terraform cannot reliably order attachment deletion before role deletion.

Correct