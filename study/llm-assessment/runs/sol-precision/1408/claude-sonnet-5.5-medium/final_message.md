The report is correct. `aws_lambda_function.webhook` takes the role ARN from `aws_iam_role.webhook_lambda`, but nothing links it to `aws_iam_role_policy_attachment.webhook_vpc_execution_role` (`webhook.tf` lines 110–114).

- **Existing references:** The function has no `depends_on`. It references only the role, not the attachment, so Terraform can create the function before the policy is attached.
- **Why order matters:** When `vpc_config` is set, Lambda creates network interfaces for the function. It needs the EC2 network-interface permissions from `AWSLambdaVPCAccessExecutionRole`, which this attachment grants. If the function is created before the policy is attached, creation can fail with a permissions error.
- **Same condition:** The attachment is created whenever `lambda_subnet_ids` is non-empty. That is the same case in which `vpc_config` is set, so the ordering gap applies exactly when the permissions are needed.

Correct