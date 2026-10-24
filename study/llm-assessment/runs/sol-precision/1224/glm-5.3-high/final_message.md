I inspected `examples/ephemeral/main.tf`, which instantiates the root module, which then instantiates `module "runner_binaries"` from `modules/runner-binaries-syncer`.

In `modules/runner-binaries-syncer/runner-binaries-syncer.tf`:

- `aws_cloudwatch_event_target.syncer` references only:
  - `aws_cloudwatch_event_rule.syncer.name`
  - `aws_lambda_function.syncer.arn`
- `aws_lambda_permission.syncer` grants `events.amazonaws.com` permission to invoke the Lambda function, scoped with `source_arn = aws_cloudwatch_event_rule.syncer.arn`.
- There is no `depends_on` from the event target to the Lambda permission.
- The event rule is enabled by default (`enable_event_rule_binaries_syncer` defaults to `true`).

AWS EventBridge needs the Lambda resource-based permission before it can successfully invoke the function. Although both resources depend on the event rule and Lambda function, Terraform treats the event target and Lambda permission as siblings, so it may create/activate the target before the permission exists. Once the target is attached to the enabled scheduled rule, EventBridge can attempt invocation before the authorization policy is present.

The reported missing dependency is therefore real and unexpressed in the configuration.

Correct