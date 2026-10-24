The report is incorrect. The ordering it asks for isn't a real requirement.

The permission and the target are independent resources. Both depend on the Lambda function and the event rule, and neither refers to the other. The target resource (`aws_cloudwatch_event_target.scale_down`) doesn't need the permission to be created. AWS doesn't check the invoke permission when a target is registered.

The permission also doesn't depend on the target. If an event fires before the permission exists, that single invocation fails. The next scheduled run succeeds once the permission is in place, so a schedule-based rule is not harmed in any lasting way. This is a transient race, not a creation-ordering requirement.

Terraform examples commonly leave this ordering unexpressed for the same reason.

Incorrect