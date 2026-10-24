## Analysis

**The reported dependency:** `aws_autoscaling_group.gitlab_runner_instance` → `aws_iam_role_policy.instance`

### What the configuration actually expresses

**`aws_autoscaling_group.gitlab_runner_instance`** (`main.tf:154`) references only:
- `aws_launch_template.gitlab_runner_instance` (name, id, latest_version) — implicit dependency on the launch template
- subnets, tags locals, and variables — no IAM resources whatsoever, and there is no `depends_on` (grep confirms the module contains zero `depends_on` declarations).

**`aws_launch_template.gitlab_runner_instance`** (`main.tf:251-253`) references the instance profile only by a **name string**: `iam_instance_profile { name = local.aws_iam_role_instance_name }`, where `local.aws_iam_role_instance_name` is `coalesce(var.runner_iam_role_name, "${local.name_iam_objects}-instance")` (`locals.tf:3-6`). This is a computed string, not a reference to `aws_iam_instance_profile.instance`, `aws_iam_role.instance`, or the policy — so Terraform has **no implicit edge** from the ASG/launch-template chain to the IAM resources at all.

**`aws_iam_role_policy.instance`** (`logging.tf:1-6`) attaches the inline CloudWatch Logs policy (`logs:CreateLogGroup/CreateLogStream/PutLogEvents/DescribeLogStreams`, per `policies/instance-logging-policy.json`) to the role name string. It is the **sole source** of CloudWatch Logs permissions for the runner instance role — no other policy attached to that role (`main.tf:355-519`) grants `logs:*`.

### Is there a concrete ordering requirement?

Yes:
- The ASG hardcodes `min_size/max_size/desired_capacity = "1"`, so **an instance launches immediately when the ASG is created**.
- `enable_cloudwatch_logging` defaults to `true` and `create_runner_iam_role` to `true` (`variables.tf:469-473, 781-785`), so by default the launch template's user-data includes `template/logging.tpl`, which **installs and starts the `awslogs` service at instance startup**, pushing logs to CloudWatch using the instance role's credentials.
- That bootstrap therefore needs the logging policy's permissions at instance startup. The target's claim is accurate: the launch template references only the profile/role name, not this policy, and nothing else in the graph orders the policy before the ASG.

Terraform is free to create the ASG (triggering instance launch and the logging bootstrap) concurrently with — or even before — `aws_iam_role_policy.instance` is attached, since the policy node has no dependency relationship with the ASG node. The only reason this works in practice is timing luck (IAM attaches within seconds and the instance's `yum install` loop delays the agent start), not any ordering Terraform enforces — and `aws_iam_role_policy.instance`'s `count` means it isn't even guaranteed to be applied in the same batch ordering. The requirement "policy attached before the runner's bootstrap logging runs" is a genuine operational ordering requirement of the default configuration (the classic boot-time IAM dependency that Terraform practitioners close with `depends_on`), and it is completely unexpressed in the current configuration.

The mitigating factors (fast IAM propagation, agent retries) make the practical race window small and self-healing, but the diagnostic's factual claims hold: the ordering requirement exists, it is not expressed through either an attribute reference or `depends_on`, and Terraform lacks the information needed to enforce it.

Correct