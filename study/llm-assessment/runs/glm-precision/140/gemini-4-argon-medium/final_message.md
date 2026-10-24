### Assessment

In `modules/webhook/eventbridge/dispatcher.tf`, `aws_lambda_function.dispatcher` (lines 23–71) and `aws_cloudwatch_log_group.dispatcher` (lines 73–79) are configured such that the log group references the Lambda function's name:

```hcl
resource "aws_cloudwatch_log_group" "dispatcher" {
  name              = "/aws/lambda/${aws_lambda_function.dispatcher.function_name}"
  retention_in_days = var.config.logging_retention_in_days
  kms_key_id        = var.config.logging_kms_key_id
  log_group_class   = var.config.log_class
  tags              = var.config.tags
}
```

This creates an implicit dependency in the wrong direction (`aws_cloudwatch_log_group.dispatcher` depends on `aws_lambda_function.dispatcher`), meaning the Lambda function is created before its CloudWatch log group:

1. **Operational / AWS behavior:** The CloudWatch log group should exist before the Lambda function can be invoked. If the function is invoked before `aws_cloudwatch_log_group.dispatcher` is created (for instance, when VPC execution role `AWSLambdaVPCAccessExecutionRole` is attached, which includes `logs:CreateLogGroup`), AWS Lambda automatically creates `/aws/lambda/<function_name>` with default settings (no retention limit, default log class, no KMS key), causing `aws_cloudwatch_log_group.dispatcher` creation to fail with `ResourceAlreadyExistsException`. When not in a VPC, the logging policy (`aws_iam_role_policy.dispatcher_logging`, which only grants `logs:CreateLogStream` and `logs:PutLogEvents` and itself waits on `aws_cloudwatch_log_group.dispatcher.arn`) is also not yet in place when the function is created, so early invocations cannot log.
2. **Configuration status:** `aws_lambda_function.dispatcher` has no dependency on `aws_cloudwatch_log_group.dispatcher`; instead, the dependency is inverted via `aws_lambda_function.dispatcher.function_name`. By deriving the log group name directly from `"${var.config.prefix}-dispatch-to-runner"` (or via a shared local) and making `aws_lambda_function.dispatcher` depend on `aws_cloudwatch_log_group.dispatcher` (via `depends_on` or `logging_config`), Terraform can enforce the proper creation and destruction order.

Correct