In `modules/terminate-instances/main.tf`, `aws_lambda_function.terminate_runner_instances` references `aws_iam_role.lambda.arn`, creating an implicit dependency only on the IAM role itself. It has no implicit or explicit (`depends_on`) dependency on `aws_iam_role_policy_attachment.lambda` in `modules/terminate-instances/iam.tf`.

Without this dependency:
1. Terraform can create `aws_lambda_function.terminate_runner_instances` and register it as the target of `aws_cloudwatch_event_target.terminate_instances` before `aws_iam_role_policy_attachment.lambda` attaches the policy granting EC2 instance lookup/termination, Auto Scaling lifecycle completion, and CloudWatch Logs permissions.
2. Because `aws_iam_role_policy_attachment.lambda` transitively depends on `aws_cloudwatch_log_group.lambda` (via `aws_iam_policy.lambda` and `data.aws_iam_policy_document.lambda`), depending on the policy attachment also guarantees that the managed CloudWatch log group exists before the Lambda function is created and potentially invoked.

Correct