I now have a complete picture. Let me summarize my analysis.

## Assessment

**The reported claim**: `aws_lambda_function.ami_housekeeper` is missing a dependency on `aws_cloudwatch_log_group.ami_housekeeper`, because the function is created *before* the log group (the log group's name references `aws_lambda_function.ami_housekeeper.function_name`), and an invocation in that window would cause Lambda to auto-create `/aws/lambda/<name>` with default settings, colliding with the Terraform-managed log group.

**Findings from the configuration** (`modules/ami-housekeeper/main.tf`, `policies/lambda-cloudwatch.json`):

1. **No creation-time requirement exists.** The Lambda `CreateFunction` API does not require or reference a CloudWatch log group; the function is created and operates fine regardless of the log group's existence.

2. **The claimed failure mode is blocked by this module's IAM configuration.** Per AWS documentation, Lambda auto-creates `/aws/lambda/<function-name>` on first invocation only "provided your execution role has the necessary permissions" (`logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`). This module's execution-role logging policy (`policies/lambda-cloudwatch.json`) grants **only** `logs:CreateLogStream` and `logs:PutLogEvents`, scoped to the Terraform-managed log group ARN — it deliberately omits `logs:CreateLogGroup`. So in the default configuration, the Lambda service **cannot** auto-create the log group; an invocation before the log group exists merely fails to deliver logs and creates no conflicting resource. Terraform's subsequent `aws_cloudwatch_log_group` create succeeds normally — no `ResourceAlreadyExistsException`, no default-settings drift. The only path to `logs:CreateLogGroup` is the opt-in VPC mode attachment of `AWSLambdaVPCAccessExecutionRole`.

3. **No meaningful window even in VPC mode.** The dependency graph creates the log group in the same apply round as the EventBridge target and the `aws_lambda_permission` (all depend only on the function/rule) — i.e., immediately after the function, concurrently with the wiring that makes it invocable. The default schedule is `rate(1 day)`. The "function invoked before log group exists" scenario would require the daily schedule to fire inside a sub-second race among concurrent API calls of the same apply round — a probabilistic tail risk, not a concrete ordering requirement, and not one that makes the function "incorrectly created or operated."

4. **This is the repo's deliberate, uniform design.** Every Lambda module in the repository (`modules/lambda`, webhook ×2, dispatcher, scale-up, scale-down, pool, ssm-housekeeper, syncer) uses the identical pattern: log group named from the function's name, scoped logging policy without `logs:CreateLogGroup`, and no `depends_on` between function and log group.

The reports' reasoning is a generic (and real) concern for codebases whose execution roles carry `AWSLambdaBasicExecutionRole`-style permissions, but its premise does not hold in this configuration. The function can be correctly created and operated without the log group pre-existing, and the existing graph already places the log group immediately after the function within the same apply. There is no genuine ordering requirement from the log group to the function that Terraform fails to express.

Incorrect