In `modules/runners/ssm-housekeeper.tf`, `aws_cloudwatch_event_target.ssm_housekeeper` attaches `aws_lambda_function.ssm_housekeeper` as a target to the scheduled rule `aws_cloudwatch_event_rule.ssm_housekeeper` (which defaults to `state = "ENABLED"`):

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

Both `aws_cloudwatch_event_target.ssm_housekeeper` and `aws_lambda_permission.ssm_housekeeper` depend on `aws_cloudwatch_event_rule.ssm_housekeeper` and `aws_lambda_function.ssm_housekeeper`, but there is no dependency between the event target and the Lambda permission. Because EventBridge (`events.amazonaws.com`) requires the resource-based policy granted by `aws_lambda_permission.ssm_housekeeper` to invoke the function, creating the event target on an enabled scheduled rule before the permission is in place can result in failed invocations if the schedule fires before the permission resource finishes creation.

Correct