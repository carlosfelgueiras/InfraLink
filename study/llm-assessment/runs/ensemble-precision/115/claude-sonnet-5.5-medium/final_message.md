The report is correct. `aws_iam_role_policy_attachment.docker_machine_cache_instance` sets `role = local.aws_iam_role_instance_name`. That local is a name string built from `var.runner_iam_role_name` or `local.name_iam_objects`, so it does not reference `aws_iam_role.instance`.

The policy ARN comes from `local.bucket_policy`. That local only references `module.cache` or a variable, so it doesn't reach the role either.

When `var.create_runner_iam_role` is true, the module creates `aws_iam_role.instance` with that same name. Terraform has no way to know the attachment must wait for it. IAM's `AttachRolePolicy` call fails with `NoSuchEntity` if the role doesn't exist yet, so the attachment can run first and fail.

I found no `depends_on` on the attachment (I only read the attachment block in `main.tf`). The cache policy attachment is the only resource of this kind that I checked.

Correct