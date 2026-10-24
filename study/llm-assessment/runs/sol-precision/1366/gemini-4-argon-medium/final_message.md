In `modules/runners/scale-down.tf`, `aws_lambda_function.scale_down` configures `role = aws_iam_role.scale_down.arn` and conditionally includes a `vpc_config` block when `var.lambda_subnet_ids` and `var.lambda_security_group_ids` are provided. The VPC access permissions (`AWSLambdaVPCAccessExecutionRole`) are attached separately via `aws_iam_role_policy_attachment.scale_down_vpc_execution_role`, which also references `aws_iam_role.scale_down`.

Because `aws_lambda_function.scale_down` only references `aws_iam_role.scale_down.arn` and has no implicit or explicit dependency (`depends_on`) on `aws_iam_role_policy_attachment.scale_down_vpc_execution_role`:
1. **Creation:** When deployed in a VPC, AWS Lambda requires the execution role to already have EC2 network interface permissions (`ec2:CreateNetworkInterface`, `ec2:DescribeNetworkInterfaces`, `ec2:DeleteNetworkInterface`) at the time `CreateFunction` is called. Without an ordering dependency, Terraform can attempt to create the Lambda function before the policy attachment completes.
2. **Deletion:** During `terraform destroy`, Terraform may detach `AWSLambdaVPCAccessExecutionRole` in parallel with or prior to deleting the Lambda function, revoking the permissions needed to clean up the VPC network interfaces.

Therefore, the reported missing dependency is valid.

Correct