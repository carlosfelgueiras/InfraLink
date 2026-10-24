I've inspected the module. Here is my assessment.

## Configuration facts (at commit `84cf54a`)

**Node — `:resource.aws_ecs_service.this`** (`modules/service/main.tf`, lines 31–211):
- `iam_role = local.iam_role_arn` refers to `aws_iam_role.service` / `var.iam_role_arn` — the *service* role (ELB registration), **not** the task-execution role.
- `task_definition = local.task_definition` → `aws_ecs_task_definition.this` → `execution_role_arn = try(aws_iam_role.task_exec[0].arn, ...)`. This creates an implicit edge only to the **role object** (`aws_iam_role.task_exec`), not to any policy attachment on it.
- The only explicit edge is `depends_on = [aws_iam_role_policy_attachment.service]` (line 204) — the policy attachment for the **service** role, a different role entirely.

**Target — `:resource.aws_iam_role_policy_attachment.task_exec_additional`** (lines 786–791):
- Attaches the user-supplied `var.task_exec_iam_role_policies` (e.g. `AmazonECSTaskExecutionRolePolicy`, scoped ECR/KMS/S3 policies) to `aws_iam_role.task_exec` — the role the ECS agent/Fargate assumes at **task launch** to pull images, fetch secrets/env files, and ship logs.
- Nothing in `aws_ecs_service.this` references it, and it is not in the service's `depends_on` list. Terraform may therefore create the service concurrently with (or before) these attachments.

## Ordering requirement

The ECS service, upon creation, immediately schedules `desired_count` (default `1`) tasks. Task launch requires the task-execution role to already carry the permissions granted by these attached policies (image pull from ECR, secret retrieval, S3 env files, log delivery) — plus IAM's eventual-consistency propagation delay, a well-known cause of `CannotPullContainerError` / "unable to pull secrets" task-launch failures on first deployment. Without an edge, the first launches can race the attachment and fail (hard failures with `wait_for_steady_state` or a circuit breaker).

Notably, the module itself already recognizes this exact race class for the *service* role: `depends_on = [aws_iam_role_policy_attachment.service]` exists so the service doesn't start registering ELB targets before its role's policy is attached. The identical operational requirement applies to the task-exec role's additional policies and the service's task launches — but that edge is absent.

The relation is not merely "two related resources": the attachment supplies permissions that are consumed at the moment the service begins operating (launching tasks), and the configuration currently gives Terraform no way to order them.

Correct