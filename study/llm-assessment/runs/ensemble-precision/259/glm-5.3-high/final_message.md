## Assessment

**The reported pair** (both in `modules/runners/scale-down.tf`, reached via `examples/multi-runner` → `modules/multi-runner/runners.tf`):

- `aws_cloudwatch_event_target.scale_down` (lines 68–71) references only `aws_cloudwatch_event_rule.scale_down.name` and `aws_lambda_function.scale_down.arn`.
- `aws_lambda_permission.scale_down` (lines 73–79) references only `aws_lambda_function.scale_down.function_name` and `aws_cloudwatch_event_rule.scale_down.arn`.

Confirmed: no attribute reference and no `depends_on` connects the target to the permission — they are siblings in the graph. So the question is purely whether a **concrete ordering requirement** exists.

**Why there is no concrete requirement:**

1. **Creation is unconditionally valid.** EventBridge's `PutTargets` API performs no validation of the Lambda resource policy. The target is created correctly and completely regardless of whether the permission exists. This is unlike the S3-notification path, where the API hard-fails without the permission.

2. **The claimed harm is a transient, self-healing bootstrap race, not an operational ordering requirement.** The rule fires every 5 minutes (`cron(*/5 * * * ? *)` default). Both sibling resources are created within the same `terraform apply`, seconds apart. For a scheduled fire to land in that sub-minute window is unlikely; if it does, EventBridge's at-least-once delivery retries it, and the permission — created moments later in the same apply — makes the retry succeed. The scale-down Lambda is an idempotent periodic cleanup sweep; during the *only* window where the race can occur (initial bootstrap) there are no runners to terminate, so a denied/retried invocation has zero functional impact. Steady-state operation is unaffected, and later applies recreate neither resource.

3. **The repo's own configuration demonstrates the distinction.** The maintainers *do* encode `depends_on = [aws_lambda_permission.on_deploy]` in `modules/runner-binaries-syncer/runner-binaries-syncer.tf` (line 170) for the S3 bucket notification — the case where AWS genuinely requires permission-first or the API call fails. They deliberately omit such ordering for all three EventBridge target/permission pairs (`scale-down`, `syncer`, `pool`), consistent with the community-standard `terraform-aws-modules/eventbridge` pattern, which also orders event targets only after their rules, never after Lambda permissions.

Ordering the target after the permission would be a defensive nicety that marginally shrinks an already-tiny, self-correcting window; it is not a requirement for either resource to be correctly created or operated, so Terraform is not "missing" information it needs to enforce correctness.

**Classification:** the reported dependency does not rise to a real ordering requirement.

Incorrect