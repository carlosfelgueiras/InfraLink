The report is correct: nothing in the configuration makes the Config recorder status wait for the `AWS_ConfigRole` attachment.

- **The recorder role:** `aws_iam_role.recorder` in `config_baselines.tf` is the root-level role. Its permissions come from two separate resources: `aws_iam_role_policy_attachment.recorder_read_policy`, which attaches `AWS_ConfigRole`, and `aws_iam_role_policy.recorder_publish_policy`.
- **How the module gets the role:** Each regional `config-baseline` module receives only `iam_role_arn = one(aws_iam_role.recorder[*].arn)`. That value depends on the role itself, not on its policy attachments.
- **Current ordering in the module:** In `modules/config-baseline/main.tf`, `aws_config_configuration_recorder.recorder` uses `var.iam_role_arn`. `aws_config_delivery_channel.bucket` depends on the recorder. `aws_config_configuration_recorder_status.recorder` depends on the delivery channel. All of these depend only on the role ARN, so Terraform can start the recorder before the policy attachment exists.
- **Why the ordering matters:** `AWS_ConfigRole` gives Config the read permissions it uses to describe resources while recording. If the recorder is started with `is_enabled = true` before that policy is attached, recording can start without those permissions. That produces failures or gaps at startup.

The ordering is a startup race rather than a hard API rejection, but it is a real operational requirement.

Correct