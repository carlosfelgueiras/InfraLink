The reported missing dependency is **Correct**.

### Analysis
In `main.tf`:
```hcl
resource "aws_iam_instance_profile" "instance" {
  count = var.create_runner_iam_role ? 1 : 0

  name = local.aws_iam_role_instance_name
  role = local.aws_iam_role_instance_name
  tags = local.tags
}

resource "aws_iam_role" "instance" {
  count                = var.create_runner_iam_role ? 1 : 0
  name                 = local.aws_iam_role_instance_name
  assume_role_policy   = length(var.instance_role_json) > 0 ? var.instance_role_json : templatefile("${path.module}/policies/instance-role-trust-policy.json", {})
  permissions_boundary = var.permissions_boundary == "" ? null : "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:policy/${var.permissions_boundary}"
  tags                 = merge(local.tags, var.role_tags)
}
```

And in `locals.tf`:
```hcl
  aws_iam_role_instance_name = coalesce(
    var.runner_iam_role_name,
    "${local.name_iam_objects}-instance"
  )
```

When `var.create_runner_iam_role` is `true`, both `aws_iam_instance_profile.instance` and `aws_iam_role.instance` are created. Creating an IAM instance profile with the `role` argument causes the AWS provider to invoke `AddRoleToInstanceProfile`, which requires the target IAM role (`aws_iam_role.instance`) to already exist in AWS.

Because `aws_iam_instance_profile.instance` sets `role = local.aws_iam_role_instance_name` (which only depends on variables/tags) and does not declare `depends_on` or reference `aws_iam_role.instance`, Terraform has no dependency edge between the two resources and can attempt to attach the role to the instance profile before the role has been created.

Correct