## Analysis

**Configuration** (`modules/runners/ssm-housekeeper.tf`, lines 66–84):

```hcl
resource "aws_cloudwatch_event_rule" "ssm_housekeeper" {
  schedule_expression = local.ssm_housekeeper.schedule_expression
  state               = local.ssm_housekeeper.state   # default "ENABLED"
}

resource "aws_cloudwatch_event_target" "ssm_housekeeper" {
  rule = aws_cloudwatch_event_rule.ssm_housekeeper.name
  arn  = aws_lambda_function.ssm_housekeeper.arn
}

resource "aws_lambda_permission" "ssm_housekeeper" {
  function_name = aws_lambda_function.ssm_housekeeper.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ssm_housekeeper.arn
}
```

**Dependency graph as expressed:**
- `aws_cloudwatch_event_target.ssm_housekeeper` → implicit deps on the event rule (via `rule`) and the Lambda function (via `arn`) only.
- `aws_lambda_permission.ssm_housekeeper` → implicit deps on the Lambda function and the event rule.
- There is **no edge** (implicit or `depends_on`) between the event target and the Lambda permission — `grep` confirms no `depends_on` exists anywhere in `modules/runners`. Terraform is free to create the target before the permission, and they may even be applied in parallel.

**Operational requirement:** The rule is created with `state = "ENABLED"` (the variable default is `"ENABLED"`). Once the rule and target both exist, EventBridge will attempt to invoke the Lambda on the schedule. Those invocations succeed only if the function's resource-based policy (`aws_lambda_permission.ssm_housekeeper`, principal `events.amazonaws.com`, scoped to the rule's ARN) is already in place. If the target is registered before the permission exists — the exact ordering Terraform currently permits — any scheduled firing in that window fails with `AccessDenied` from Lambda, and the housekeeping run is dropped (EventBridge retry is limited and won't help if the permission apply fails or is delayed). The housekeeper deletes stale runner tokens/JIT config, so a silently failed invocation is operationally harmful. The required direction is exactly as reported: the permission (target) must be ready before the event target (node) begins operating, and the correct fix is a `depends_on = [aws_lambda_permission.ssm_housekeeper]` on the event target (which also subsumes the rule/function ordering already present).

The same latent race exists for `scale_down`, but that doesn't change the assessment for this pair: the ordering requirement from `aws_lambda_permission.ssm_housekeeper` → `aws_cloudwatch_event_target.ssm_housekeeper` is concrete, and the configuration does not currently express it.

All three diagnostic descriptions accurately identify this race condition and the correct direction of the dependency.

Correct