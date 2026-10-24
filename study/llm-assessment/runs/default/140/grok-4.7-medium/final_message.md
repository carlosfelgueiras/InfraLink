The event target does not need to wait on the Lambda permission. `aws_cloudwatch_event_target.ssm_housekeeper` only references the rule name and the function ARN. `aws_lambda_permission.ssm_housekeeper` is a separate resource, and nothing in the module creates an implicit or explicit edge from the target to that permission.

That missing edge is not a required ordering. `PutTargets` succeeds without a Lambda resource policy. EventBridge checks `lambda:InvokeFunction` only when it invokes the function, not when the target is registered. HashiCorp documents that permission as necessary for invocation, and only requires `depends_on` when the create call itself fails without it (for example, a CloudWatch Logs subscription filter). This module already does that for S3 notifications, and does not do it for this EventBridge target or the same pattern on scale-down and AMI housekeeper.

The rule is a legacy scheduled rule, default `rate(1 day)` and `ENABLED`. A rate expression starts a countdown at rule creation and first runs after that interval, not when the target is added. Both resources are created in the same apply, so the permission exists long before the first scheduled run. A tighter user schedule could theoretically overlap the apply window, but that is not a concrete requirement that the target cannot be created or operated without the permission already existing. Failed deliveries are also retried for up to 24 hours.

The two resources are related, but the target does not have to be ordered after the permission.

Incorrect