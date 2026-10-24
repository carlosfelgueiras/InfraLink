## Analysis

**Configuration facts** (`modules/runners/scale-down.tf`):

1. **`aws_lambda_function.scale_down` (lines 11–64)**: references only `aws_iam_role.scale_down.arn` (line 18). Its `vpc_config` block (lines 50–56) uses only plain variables (`var.lambda_subnet_ids`, `var.lambda_security_group_ids`) with no resource references. `filename`/`source_code_hash` reference only a local file path.

2. **`aws_iam_role_policy_attachment.scale_down_vpc_execution_role` (lines 123–127)**: attaches the AWS-managed `AWSLambdaVPCAccessExecutionRole` policy (which includes `ec2:CreateNetworkInterface`, `ec2:DescribeNetworkInterfaces`, `ec2:DeleteNetworkInterface`, `ec2:AssignPrivateIpAddresses`, etc.) to the same role, created when `lambda_subnet_ids` is non-empty.

3. Terraform's graph therefore only orders *both* resources after `aws_iam_role.scale_down`; the function and the attachment are **unordered relative to each other** and can be created in parallel. A grep confirms there is no `depends_on` anywhere in `modules/runners`.

**Real-world ordering requirement** (per current AWS Lambda documentation):

- When a function is attached to a VPC, Lambda provisions a Hyperplane ENI *using the execution role's EC2 permissions*. AWS explicitly states that when using the CLI/API (as Terraform does), you must "make sure that your function's execution role has the necessary permissions" **before** attaching it to the VPC — a documented precondition, i.e., an ordering requirement from the attachment to the function.
- "For new functions, while Lambda is creating a Hyperplane ENI, your function remains in the Pending state and you can't invoke it." If the role lacks the ENI permissions at attach time, ENI provisioning fails and the function cannot become operational. This matches the report's claim that Lambda "can attempt to provision network interfaces before the execution role has the required EC2 permissions."
- On the deletion side, AWS also documents: "Lambda relies on permissions in the function execution role to delete the Hyperplane ENI." With no `depends_on`, destroy order between the attachment and the function is unspecified, so the policy could be detached before Lambda finishes cleaning up the function's ENI — matching the report's second rationale.

**Corroborating practice**: the widely used reference module `terraform-aws-modules/lambda` explicitly declares `depends_on` from `aws_lambda_function` to all `aws_iam_role_policy` and `aws_iam_role_policy_attachment` resources, with the comment "Before the lambda is created the execution role with all its policies should be ready" — confirming this is a recognized ordering requirement, not merely a stylistic association.

**Conclusion**: When `scale_down` is deployed in a VPC, the `AWSLambdaVPCAccessExecutionRole` attachment must be in place before the function is created/attached (and should outlive it during deletion), and Terraform currently has no way to enforce that ordering — the `role` ARN reference orders only the role, not this separate attachment. The report is accurate.

Correct