I now have the complete picture. Let me verify my analysis of the dependency graph in `modules/runners/pool/main.tf`:

**Resources involved:**

1. `aws_iam_role.scheduler` (line 204) — the execution role EventBridge Scheduler assumes, with trust policy restricted to `scheduler.amazonaws.com` and `aws:SourceArn = aws_scheduler_schedule_group.pool.arn`.

2. `aws_iam_role_policy.scheduler` (line 214) — the inline policy granting `lambda:InvokeFunction` on `aws_lambda_function.pool.arn` (policy document at lines 196–202, SID `InvokePoolLambda`). This is the **only** permission allowing the scheduler role to invoke the pool Lambda.

3. `aws_scheduler_schedule.pool` (line 220) — the schedule targeting `aws_lambda_function.pool.arn` via `role_arn = aws_iam_role.scheduler.arn`.

**Dependency analysis:**

The schedule references only `aws_scheduler_schedule_group.pool` (group_name), `aws_lambda_function.pool` (target arn), and `aws_iam_role.scheduler` (role_arn). It does **not** reference `aws_iam_role_policy.scheduler` in any attribute, and there is no `depends_on` anywhere in the pool module. The role policy and the schedule are siblings in the DAG (both depend on the role/Lambda), so Terraform may create them in parallel or in either order — it has no information enforcing policy-before-schedule.

**Is there a concrete ordering requirement?**

- `aws_scheduler_schedule` sets no `state` attribute, so it defaults to `ENABLED` — the schedule is active immediately upon creation and fires per its `schedule_expression`.
- EventBridge Scheduler does not validate target permissions at schedule creation time; it only assumes the role and calls `lambda:InvokeFunction` at invocation time. If the schedule fires before `aws_iam_role_policy.scheduler` is attached, every such invocation is denied with an access-denied failure (visible as failed invocations in the Scheduler log group, not as a Terraform error).
- The pool Lambda is invoked *exclusively* through this role policy — there is no other grant of `lambda:InvokeFunction` to the scheduler principal. So until the policy exists, the enabled schedule cannot operate correctly at all, and any early firing within the apply window is lost/denied.

Since the schedule is enabled the moment it's created, the role policy must be in place first. This is a real operational ordering requirement (target → node), and it is currently unexpressed in the configuration. The reports' descriptions ("enabled schedule can invoke the pool Lambda before Scheduler's invocation policy is installed", "scheduled invocations denied") accurately describe this gap.

Correct