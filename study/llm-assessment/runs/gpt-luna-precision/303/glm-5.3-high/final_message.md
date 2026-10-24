## Assessment

**Node:** `aws_ecs_service.this` (modules/service/main.tf:31)
**Target:** `aws_iam_role_policy.tasks` (modules/service/main.tf:1017)

### Is the ordering requirement real?

Yes. When `aws_ecs_service.this` is created (with a non-external deployment controller and `desired_count > 0`, or DAEMON scheduling), ECS immediately launches tasks using the task definition, whose `task_role_arn` points at `aws_iam_role.tasks`. The inline policy `aws_iam_role_policy.tasks` is what actually grants that role its task-level permissions — it is created whenever `tasks_iam_role_statements` are supplied or `enable_execute_command` is true (which injects the `ssmmessages:*` permissions required for ECS Exec). If tasks start before the inline policy is installed, they run with an unauthorized task role: application API calls fail with `AccessDenied`, `execute-command` breaks, and with `wait_for_steady_state = true` or the deployment circuit breaker enabled the apply/deployment outright fails. So the policy must be in place before the service starts tasks — a concrete operational ordering requirement, not mere relatedness.

The module itself demonstrates that its maintainers consider exactly this class of ordering necessary: `aws_ecs_service.this` already carries `depends_on = [aws_iam_role_policy_attachment.service]` (main.tf:204) so the *service* role's ELB permissions are attached before the service operates.

### Is the dependency currently expressed?

No. The service's reference graph includes:
- `local.task_definition` → `aws_ecs_task_definition.this` → `aws_iam_role.tasks` (the **role** ARN only, which exists before any inline policy is applied),
- `local.iam_role_arn` → `aws_iam_role.service`,
- `depends_on = [aws_iam_role_policy_attachment.service]`.

Nothing references `aws_iam_role_policy.tasks` from the service. `aws_iam_role_policy.tasks` and `aws_ecs_service.this` are siblings that both depend on `aws_iam_role.tasks`/the task definition chain, so Terraform is free to create the service (and start tasks) concurrently with — or before — the inline policy. The same gap exists for the task-exec attachments, but the reported target `aws_iam_role_policy.tasks` is indeed uncovered.

### Conclusion

The report is correct: tasks launched by the ECS service require the task-role inline permissions, and Terraform currently has no implicit or explicit edge enforcing that `aws_iam_role_policy.tasks` is applied before `aws_ecs_service.this` is created and starts tasks.

Correct