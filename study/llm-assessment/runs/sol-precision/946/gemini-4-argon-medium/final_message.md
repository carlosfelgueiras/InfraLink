In `main.tf`, `aws_launch_template.gitlab_runner_instance` configures its IAM instance profile using a local string value rather than referencing the `aws_iam_instance_profile.instance` resource:

```hcl
  iam_instance_profile {
    name = local.aws_iam_role_instance_name
  }
```

Meanwhile, `aws_iam_instance_profile.instance` (created when `var.create_runner_iam_role` is `true`, the default) also sets `name = local.aws_iam_role_instance_name`, and is not referenced anywhere in the configuration:

```hcl
resource "aws_iam_instance_profile" "instance" {
  count = var.create_runner_iam_role ? 1 : 0

  name = local.aws_iam_role_instance_name
  role = local.aws_iam_role_instance_name
  tags = local.tags
}
```

Because `local.aws_iam_role_instance_name` is derived purely from input variables (`var.runner_iam_role_name`, `var.overrides`, and `var.environment`), Terraform has no implicit or explicit dependency edge between `aws_launch_template.gitlab_runner_instance` and `aws_iam_instance_profile.instance`. As a result, `aws_launch_template.gitlab_runner_instance` (and the downstream `aws_autoscaling_group.gitlab_runner_instance` that depends on it) can be created before the IAM instance profile exists.

Correct