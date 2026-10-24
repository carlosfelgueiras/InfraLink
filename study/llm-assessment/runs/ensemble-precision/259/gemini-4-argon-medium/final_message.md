In `modules/runners/scale-down.tf`, `aws_cloudwatch_event_target.scale_down` and `aws_lambda_permission.scale_down` both reference `aws_cloudwatch_event_rule.scale_down` and `aws_lambda_function.scale_down`:

```hcl
resource "aws_cloudwatch_event_target" "scale_down" {
  rule = aws_cloudwatch_event_rule.scale_down.name
  arn  = aws_lambda_function.scale_down.arn
}

resource "aws_lambda_permission" "scale_down" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scale_down.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scale_down.arn
}
```

Unlike services such as S3 bucket notifications (which validate Lambda invoke permissions during configuration), the EventBridge `PutTargets` API (`aws_cloudwatch_event_target`) does not require the Lambda resource-based permission (`aws_lambda_permission`) to exist before registering the target. Furthermore, EventBridge automatically retries failed target invocations with backoff if a rule triggers during the brief window while the permission is being applied concurrently, and the scale-down function itself is a periodic cleanup task. Consequently, no ordering dependency from `aws_lambda_permission.scale_down` to `aws_cloudwatch_event_target.scale_down` is required.

Incorrect