## Analysis

**Configuration facts** (module root = `source = "../../"` from `examples/runner-docker`):

- `aws_autoscaling_group.gitlab_runner_instance` (`main.tf:188`) references only `aws_launch_configuration.gitlab_runner_instance.name`.
- The launch configuration (`main.tf:221`) references `aws_iam_instance_profile.instance.name`, which references `aws_iam_role.instance.name`.
- `aws_iam_role_policy.instance` (`logging.tf:6`) is a *separate* resource that attaches the inline CloudWatch logging policy (grants `logs:CreateLogGroup/CreateLogStream/PutLogEvents/DescribeLogStreams`) to `aws_iam_role.instance`. It exists by default: `enable_cloudwatch_logging` defaults to `true` (`variables.tf:280-283`) and the example does not override it.
- Grep confirms `aws_iam_role_policy.instance` is referenced nowhere outside `logging.tf`, and there is no `depends_on` in the module.

**Dependency chain today:** ASG → launch configuration → instance profile → IAM role. The role policy also hangs off the role, but nothing orders it before the ASG. Terraform can create the ASG (which immediately launches an instance, `desired_capacity = 1`) concurrently with or before the policy is attached.

**Operational requirement:** The instance user data (`template/user-data.tpl:20` → `template/logging.tpl`) is injected when logging is enabled and, at boot, installs `awslogs`, writes `/etc/awslogs/awslogs.conf` (publishing `dmesg`, `messages`, and `user-data.log` to CloudWatch Logs), and runs `service awslogs start`. The agent authenticates via the instance role and needs exactly the permissions granted by `aws_iam_role_policy.instance` from that moment on. If the ASG launches the instance before the policy is attached, the agent's CloudWatch API calls fail with `AccessDenied` during initialization — a real startup race between log delivery/policy attachment that the configuration does not and cannot currently enforce, since no attribute reference or `depends_on` links the ASG (or launch configuration) to the inline policy.

The report is accurate in both respects: there is a concrete ordering requirement (policy must be attached to the role before instances boot and initialize logging), and Terraform currently lacks the information to enforce it. A `depends_on = [aws_iam_role_policy.instance]` on the ASG would be the appropriate fix.

Correct