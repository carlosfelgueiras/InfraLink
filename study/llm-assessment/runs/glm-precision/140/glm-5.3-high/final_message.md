I've now verified all the key facts. Let me summarize my analysis.

## Analysis

**Current configuration (`modules/webhook/eventbridge/dispatcher.tf`):**

```hcl
resource "aws_lambda_function" "dispatcher" {          # line 23
  function_name = "${var.config.prefix}-dispatch-to-runner"  # line 29
  ...
}
resource "aws_cloudwatch_log_group" "dispatcher" {    # line 73
  name = "/aws/lambda/${aws_lambda_function.dispatcher.function_name}"  # line 74
  ...
}
```

The only dependency expressed between them is **reversed**: the log group implicitly depends on the function (via `function_name` at line 74). The function has no attribute reference to, and no `depends_on` on, the log group. So Terraform creates the function **first** and the log group **after** — the opposite of the reported direction.

**Real-world ordering requirement:**

- AWS Lambda creates `/aws/lambda/<function-name>` **lazily, at first invocation** (confirmed in AWS docs: *"CloudWatch automatically creates a log group named `/aws/lambda/<function name>` ... when it's first invoked"*), with defaults — retention never expires, no customer KMS key — so the configured `retention_in_days` (default 180), `kms_key_id`, `log_group_class`, and `tags` would never apply to the auto-created group.
- The dispatcher function is event-driven: `aws_cloudwatch_event_target.dispatcher` targets `aws_lambda_function.dispatcher.arn`, with `aws_lambda_permission` for `events.amazonaws.com`, and the webhook lambda publishes `workflow_job` events to the bus. Nothing orders the log group ahead of the event target, so the function can begin receiving invocations before the log group resource exists.
- If that happens, the subsequent `aws_cloudwatch_log_group` create fails with `ResourceAlreadyExistsException` (the provider does not adopt an existing group — a documented failure mode, e.g. hashicorp/terraform-provider-aws#18468), breaking the apply.

**Fix is technically sound:** the function name is fully computable from `var.config.prefix`, so the log group name can be decoupled from the function (as the report says, keeping the name reference would make a bare `depends_on` a graph cycle), and the function can then depend on the log group via `depends_on` or `logging_config.log_group` (available in the pinned provider `>= 6.21`). This is exactly the canonical handling in the official `terraform-aws-modules/terraform-aws-lambda`, whose `aws_lambda_function` carries `depends_on = [aws_cloudwatch_log_group.lambda]` with the comment: *"Depending on the log group is necessary to allow Terraform to create the log group before AWS can... race condition if the lambda function is invoked before Terraform can create the log group."*

So: the log group (target) must be created before the function (node) can be correctly operated, and Terraform currently not only lacks that ordering information but encodes the reverse ordering.

Correct