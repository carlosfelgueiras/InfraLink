The reported missing dependency is **Correct**.

### Analysis
1. **Operational Requirement**:
   `aws_instance.bootstrap_node` assumes the IAM role `aws_iam_role.elasticsearch` via `aws_iam_instance_profile.elasticsearch`. Immediately upon boot, its `user_data` script (`templates/user_data.sh`) invokes `aws ec2 describe-instances` and starts Elasticsearch configured with `plugin.mandatory: discovery-ec2`. Both the bootstrap script and the Elasticsearch EC2 discovery plugin require the `ec2:DescribeInstances` permission granted by `aws_iam_role_policy.elasticsearch` (`templates/ec2-allow-describe-instances.json`).

2. **Missing Terraform Dependency**:
   In `terraform-aws/iam.tf` and `terraform-aws/masters.tf`:
   - `aws_iam_instance_profile.elasticsearch` references `aws_iam_role.elasticsearch.name`.
   - `aws_iam_role_policy.elasticsearch` references `aws_iam_role.elasticsearch.id`.
   - `aws_instance.bootstrap_node` references `aws_iam_instance_profile.elasticsearch.id` (directly and transitively via `aws_autoscaling_group.master_nodes` -> `aws_launch_configuration.master`), but has neither an implicit nor an explicit dependency on `aws_iam_role_policy.elasticsearch`.

Because `aws_iam_role_policy.elasticsearch` and `aws_iam_instance_profile.elasticsearch` are independent branches off `aws_iam_role.elasticsearch`, Terraform can launch `aws_instance.bootstrap_node` before the inline policy is attached to the role.

Correct