To assess the reported missing dependency, we examine the resources in `modules/runners/scale-down.tf` (instantiated via `examples/windows/main.tf` -> `main.tf` (`module.runners`) -> `modules/runners` (`module.runners`)).

### Resource Configuration Analysis

In `modules/runners/scale-down.tf`:

1. **`aws_lambda_function.scale_down`** (lines 8–53):
   - References `role = aws_iam_role.scale_down.arn`.
   - Includes a dynamic `vpc_config` block when `var.lambda_subnet_ids != null && var.lambda_security_group_ids != null`:
     ```hcl
     dynamic "vpc_config" {
       for_each = var.lambda_subnet_ids != null && var.lambda_security_group_ids != null ? [true] : []
       content {
         security_group_ids = var.lambda_security_group_ids
         subnet_ids         = var.lambda_subnet_ids
       }
     }
     ```
   - Has no reference to or `depends_on` declaration for `aws_iam_role_policy_attachment.scale_down_vpc_execution_role`.

2. **`aws_iam_role_policy_attachment.scale_down_vpc_execution_role`** (lines 107–111):
   ```hcl
   resource "aws_iam_role_policy_attachment" "scale_down_vpc_execution_role" {
     count      = length(var.lambda_subnet_ids) > 0 ? 1 : 0
     role       = aws_iam_role.scale_down.name
     policy_arn = "arn:${var.aws_partition}:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
   }
   ```

### Operational and Provider Semantics

- When a Lambda function is configured with `vpc_config`, the AWS Lambda service provisions Hyperplane Elastic Network Interfaces (ENIs) in the specified subnets during function creation (and deletes them upon function deletion or VPC config removal).
- To perform these operations, AWS Lambda assumes the function's execution role (`aws_iam_role.scale_down`) and requires EC2 network interface permissions (`ec2:CreateNetworkInterface`, `ec2:DescribeNetworkInterfaces`, `ec2:DeleteNetworkInterface`), which are provided by the `AWSLambdaVPCAccessExecutionRole` managed policy attached via `aws_iam_role_policy_attachment.scale_down_vpc_execution_role`.
- Because both `aws_lambda_function.scale_down` and `aws_iam_role_policy_attachment.scale_down_vpc_execution_role` only depend on `aws_iam_role.scale_down`, Terraform may attempt to create the Lambda function before attaching the policy (or detach the policy before destroying the Lambda function), causing creation or destruction to fail due to insufficient permissions.

Therefore, `aws_lambda_function.scale_down` requires an explicit dependency on `aws_iam_role_policy_attachment.scale_down_vpc_execution_role` that is currently missing.

Correct