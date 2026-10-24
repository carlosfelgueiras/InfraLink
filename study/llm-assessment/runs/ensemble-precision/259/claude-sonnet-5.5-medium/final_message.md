The report is incorrect. The target is not required before the node, and the configuration doesn't need to express that ordering.

The two resources in `modules/runners/scale-down.tf` don't depend on each other. `aws_cloudwatch_event_target.scale_down` uses the rule name and the Lambda ARN. `aws_lambda_permission.scale_down` uses the Lambda function name and the rule ARN. Terraform can therefore create them in parallel.

Creating the target before the permission exists is harmless. EventBridge accepts a target without checking the Lambda resource policy. The rule runs on a schedule, so the only effect is that an invocation in the brief gap between the two creations could fail. That is a short, self-correcting transient, and it is not a required ordering. The Lambda also has no real invocations until the schedule fires, and a failed first run would just be retried at the next interval.

Incorrect