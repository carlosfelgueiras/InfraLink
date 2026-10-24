## Analysis

**Configuration facts** (`modules/runners/scale-down.tf`):

- `aws_lambda_function.scale_down` (line 8) references only `aws_iam_role.scale_down.arn` (line 15) in its `role` attribute. Its `vpc_config` block (lines 39–45) is emitted when `var.lambda_subnet_ids`/`var.lambda_security_group_ids` are set, but references only the raw variables — no resource attributes.
- `aws_iam_role_policy_attachment.scale_down_vpc_execution_role` (lines 107–111) attaches `AWSLambdaVPCAccessExecutionRole` to the same role, with `count = length(var.lambda_subnet_ids) > 0`.
- There is no attribute reference from the function to the attachment and no `depends_on` (a repo-wide grep shows `depends_on` used only twice in `modules/runner-binaries-syncer`, for unrelated S3-notification ordering; the same missing edge exists for `scale_up`, webhook, and pool lambdas).

So both resources depend only on `aws_iam_role.scale_down`; Terraform has no information ordering the attachment before the function, and may create them concurrently or in the wrong order on first apply when subnets are configured.

**Real-world ordering requirement** (confirmed via AWS Lambda docs):

- "To attach a Lambda function to a VPC, Lambda needs permissions to create and manage the network interfaces it uses" — granted by attaching `AWSLambdaVPCAccessExecutionRole` (ec2:CreateNetworkInterface/Describe/Delete, etc.) to the execution role.
- When a function is created with `VpcConfig`, Lambda provisions Hyperplane ENIs as part of function creation; until ENI creation succeeds the function remains Pending and non-invocable. The documented failure mode is `StateReasonCode: InsufficientRolePermissions` — the well-known "the provided execution role does not have permissions to call CreateNetworkInterface on EC2" error. If the function is created before the policy attachment is applied, ENI provisioning fails and the function cannot be correctly created or operated.
- On cleanup, "Lambda relies on permissions in the function execution role to delete the Hyperplane ENI" — removing the attachment before the function is deleted can strand ENIs.

This is precisely why the ecosystem convention (Serverless, SAM auto-attaching the managed policy, many Terraform modules) is to order the policy attachment before VPC-connected function creation, typically via `depends_on = [aws_iam_role_policy_attachment.scale_down_vpc_execution_role]`.

**Assessment**: The operational requirement is concrete — when Lambda subnets are configured, the `AWSLambdaVPCAccessExecutionRole` attachment must be in place before the scale-down function's VPC ENIs can be provisioned (and retained for ENI cleanup). The configuration expresses only the role reference, which orders the role but not its policy attachment, and no `depends_on` exists. Terraform therefore lacks the information needed to enforce the required ordering.

Correct