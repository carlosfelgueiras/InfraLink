## Assessment

**Configuration facts** (verified at commit `4d3cbd46`):

**Node** — `aws_config_configuration_recorder_status.recorder` (`modules/config-baseline/main.tf:61-66`), which calls `StartConfigurationRecorder`. Its current dependency chain:
- `name = aws_config_configuration_recorder.recorder.id` → recorder → `var.iam_role_arn` → root `aws_iam_role.recorder` (implicit)
- `depends_on = [aws_config_delivery_channel.bucket]` → SNS topic + recorder (explicit)

**Target** — `aws_iam_role_policy.recorder_publish_policy` (`config_baselines.tf:80-86`), which grants the Config role S3 write/list/get-acl on the audit bucket path, `sns:Publish` on all regional config topics, and KMS permissions. It depends on the root `aws_iam_role.recorder` and (via `local.config_topics`) on every regional module's `config_sns_topic` output.

It's true that no path connects the target to the node — the dependency is genuinely unexpressed. However, that alone doesn't make the report correct.

**Why the claimed ordering requirement doesn't hold:**

1. **`StartConfigurationRecorder` has no permission precondition.** The AWS API reference documents exactly three errors for this call: recorder doesn't exist, `NoAvailableDeliveryChannelException` (no delivery channel), and `UnmodifiableEntityException` (service-linked recorder). It does **not** validate the role's S3/SNS/KMS delivery permissions — the call succeeds without the policy attached. The recorder then records configuration items normally; recording itself needs no delivery permissions.

2. **The one concrete API-level precondition is already enforced.** The provider docs note only that "Starting Configuration Recorder requires a Delivery Channel to be present. Use of `depends_on` ... is recommended to avoid race conditions" — and the module already does exactly that (`depends_on = [aws_config_delivery_channel.bucket]`). The delivery channel in turn already orders after the recorder (role included) and the SNS topic.

3. **Delivery failures, if any, are transient and self-healing.** Snapshots are delivered on the delivery-frequency cycle (`One_Hour` default), not synchronously at start; stream notifications are authorized by the regional topic policy (`config-sns-policy` grants `config.amazonaws.com` `sns:Publish`), independent of the role policy. Both resources complete within the same `terraform apply` (seconds apart), well before the first scheduled snapshot delivery, and Config retries deliveries on its cycle regardless.

4. **Terraform ordering couldn't enforce it anyway.** IAM policy attachment is eventually consistent, so even an explicit ordering of the status after the policy would not guarantee the permission is effective at the moment `StartConfigurationRecorder` runs — underscoring that this is a soft best-practice preference, not a concrete ordering requirement from target to node.

The report is a semantic-relationship false positive: the policy is related to the recorder's role, but `recorder_publish_policy` is not something that "must be created... before node can be correctly created or operated" — the node activates successfully and operates correctly without it, and the only real ordering requirement (delivery channel before start) is already expressed in the configuration.

Incorrect