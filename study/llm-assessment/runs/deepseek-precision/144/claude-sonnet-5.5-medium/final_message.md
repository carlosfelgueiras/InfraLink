The report is correct. The invoke permission is a real prerequisite for the schedule, and the configuration doesn't order it.

- **What the schedule needs:** `aws_scheduler_schedule.pool` invokes the pool Lambda through `aws_iam_role.scheduler`. That role can only invoke the function because of the separate inline policy `aws_iam_role_policy.scheduler`, which grants `lambda:InvokeFunction`.
- **What orders the schedule today:** it references only the role's ARN, so it waits for the role. Nothing in the schedule ties it to the policy.
- **Why Terraform can create it too early:** the policy depends on the policy document, which needs the Lambda ARN, and on the role name. The schedule has no edge to the policy, so Terraform can create them in parallel or in either order.
- **Consequence:** a schedule created before the policy takes effect can fire without permission and fail its first invocation. IAM changes are also eventually consistent, which makes this window more likely.

I didn't check provider documentation, so the first-fire behavior comes from how the configuration is wired, not from a confirmed provider detail.

The fix is `depends_on = [aws_iam_role_policy.scheduler]` on the schedule.

Correct