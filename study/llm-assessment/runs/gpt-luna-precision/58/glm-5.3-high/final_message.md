## Assessment

**Source:** `aws_iam_role_policy_attachment.instance_docker_machine_policy` (main.tf, lines 367–372)
**Target:** `aws_iam_role.instance` (main.tf, lines 342–348)

### Configuration analysis

```hcl
resource "aws_iam_role" "instance" {
  count = var.create_runner_iam_role ? 1 : 0
  name  = local.aws_iam_role_instance_name
  ...
}

resource "aws_iam_role_policy_attachment" "instance_docker_machine_policy" {
  count = var.create_runner_iam_role ? 1 : 0

  role       = local.aws_iam_role_instance_name
  policy_arn = aws_iam_policy.instance_docker_machine_policy[count.index].arn
}
```

`local.aws_iam_role_instance_name` (locals.tf, lines 3–6) is computed purely from `var.runner_iam_role_name` and `local.name_iam_objects` — it is a plain string, **not** a reference to `aws_iam_role.instance`. So no implicit dependency is created.

I checked for a transitive dependency path: the attachment references `aws_iam_policy.instance_docker_machine_policy`, but that policy references `aws_iam_role.docker_machine.arn` — a *different* role, not `aws_iam_role.instance`. A repo-wide search confirms there is no `depends_on` anywhere in the module. Therefore Terraform has **no ordering edge** (implicit or explicit) from the attachment to `aws_iam_role.instance`.

### Operational ordering requirement

When `create_runner_iam_role = true`, both resources exist and the attachment targets the very role that `aws_iam_role.instance` creates (same deterministic name). The AWS `AttachRolePolicy` API fails with `NoSuchEntity` if the role does not yet exist, so the role must be created before the attachment can succeed. Since the `role` argument is a locally computed string rather than an attribute reference (`aws_iam_role.instance[0].name`), Terraform may attempt the attachment concurrently with (or before) role creation, producing a race that can fail the apply. The required ordering is real and currently unexpressed.

(When `create_runner_iam_role = false`, both resources have `count = 0`, so the scenario doesn't arise — the problem is precisely in the case where both are created.)

The report is accurate: there is a genuine target→node ordering requirement (role must exist before policy attachment) and Terraform lacks the dependency information to enforce it.

Correct