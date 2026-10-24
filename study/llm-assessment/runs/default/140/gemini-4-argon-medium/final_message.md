In `modules/runners/ssm-housekeeper.tf`, `aws_cloudwatch_event_target.ssm_housekeeper` registers the Lambda function (`aws_lambda_function.ssm_housekeeper`) as a target for the scheduled EventBridge rule (`aws_cloudwatch_event_rule.ssm_housekeeper`), which is `ENABLED` by default (`rate(1 day)`).

```hcl
resource "aws_cloudwatch_event_target" "ssm_housekeeper" {
  rule = aws_cloudwatch_event_rule.ssm_housekeeper.name
  arn  = aws_lambda_function.ssm_housekeeper.arn
}

resource "aws_lambda_permission" "ssm_housekeeper" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ssm_housekeeper.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ssm_housekeeper.arn
}
```

Both `aws_cloudwatch_event_target.ssm_housekeeper` and `aws_lambda_permission.ssm_housekeeper` depend on `aws_cloudwatch_event_rule.ssm_housekeeper` and `aws_lambda_function.ssm_housekeeper`, so Terraform can create them concurrently in either order. Because EventBridge `rate(...)` schedules can trigger immediately once a target is attached to an enabled rule, creating `aws_cloudwatch_event_target.ssm_housekeeper` before `aws_lambda_permission.ssm_housekeeper` allows EventBridge to attempt an invocation before the resource-based Lambda permission is in place, resulting in failed invocations. Ordering `aws_cloudwatch_event_target.ssm_housekeeper` after `aws_lambda_permission.ssm_housekeeper` is required and currently missing.

Correct