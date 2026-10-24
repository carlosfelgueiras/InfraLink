## Assessment

**Reported dependency:** `aws_lambda_function.syncer` should depend on `aws_iam_role_policy_attachment.syncer_vpc_execution_role` (in `modules/runner-binaries-syncer/runner-binaries-syncer.tf`).

### What the configuration shows

**`aws_lambda_function.syncer`** (lines 10–54):
- Implicit dependencies: `aws_iam_role.syncer_lambda.arn` (role), `aws_s3_bucket.action_dist` (env vars), plus `var.lambda_subnet_ids` / `var.lambda_security_group_ids` (inputs, no resource references).
- `vpc_config` block is emitted when `var.lambda_subnet_ids != null && var.lambda_security_group_ids != null`.

**`aws_iam_role_policy_attachment.syncer_vpc_execution_role`** (lines 132–136):
- Created when `length(var.lambda_subnet_ids) > 0`; attaches the AWS-managed `AWSLambdaVPCAccessExecutionRole` policy to `aws_iam_role.syncer_lambda`.

Both resources share only the IAM role as a common dependency. There is **no attribute reference** from the function to the attachment and **no `depends_on`** — Terraform is free to create them in parallel (the function typically even wins the race, since the attachment is slower to order). The same pattern exists for the webhook, scale-up, scale-down, and pool lambdas; none of them order against their VPC attachment. In the literal `examples/default` values, `lambda_subnet_ids` defaults to `[]` so neither VPC feature is active, but the report explicitly addresses the VPC-enabled configuration of the module, where both resources exist (count = 1).

### Is the ordering requirement real?

Yes. Concrete evidence:

1. **AWS API behavior at creation time:** During `CreateFunction` with a `VpcConfig`, the Lambda service validates ENI-creation capability by performing a dry-run `CreateNetworkInterface` using the **execution role's** credentials (visible in CloudTrail, per the AWS re:Post thread "Lambda VPC deployment error"). If the role lacks `ec2:CreateNetworkInterface` etc., the function fails with `InvalidParameterValueException: The provided execution role does not have permissions to call CreateNetworkInterface on EC2`, or the provider waits on a function that transitions to a terminal `Failed` state with `InsufficientRolePermissions`. The AWS docs confirm: "The Amazon EC2 permissions that you grant to your function's execution role are used by the Lambda service to attach your function to a VPC."

2. **Documented Terraform race conditions:** 
   - `terraform-aws-modules/terraform-aws-lambda` issue #326 reports exactly this failure — a VPC Lambda created before its policy attachment fails with the `CreateNetworkInterface` error — and it was fixed in v4.0.1 by making the function depend on the policy attachments (PR #327).
   - `hashicorp/terraform-provider-aws` issue #29828 reports the same race between `aws_lambda_function` with `vpc_config` and the `AWSLambdaVPCAccessExecutionRole` attachment, with users confirming `depends_on = [aws_iam_role_policy_attachment...]` resolves it. HashiCorp's own provider docs use this pattern (`depends_on` on role policy attachments) for the logging policy for the same reason.

The AWS note that a function can still be invoked after the permissions are *removed* only applies once the Hyperplane ENI already exists; it does not negate the creation-time requirement. The ENI is provisioned as part of function creation/first configuration, and the `aws_lambda_function` resource waits for the function to reach `Active` — which it cannot do if the role lacks ENI permissions when that provisioning runs.

### Conclusion

For a VPC-attached syncer function, the `AWSLambdaVPCAccessExecutionRole` policy must be attached to the execution role before Lambda can complete function provisioning (ENI validation/creation), and Terraform currently has no way to enforce that ordering — the dependency is neither implicit (no attribute reference) nor explicit (no `depends_on`). The reports accurately describe a real, operationally demonstrated missing dependency.

Correct