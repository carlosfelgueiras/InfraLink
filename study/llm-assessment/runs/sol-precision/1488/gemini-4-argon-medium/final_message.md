In `modules/config-baseline/main.tf` (instantiated by `module.config_baseline_eu-north-1` in `config_baselines.tf`), `aws_config_delivery_channel.bucket` configures AWS Config to publish notifications to `aws_sns_topic.config`:

```hcl
resource "aws_sns_topic_policy" "config" {
  arn    = aws_sns_topic.config.arn
  policy = data.aws_iam_policy_document.config-sns-policy.json
}

resource "aws_config_delivery_channel" "bucket" {
  name           = var.delivery_channel_name
  s3_bucket_name = var.s3_bucket_name
  s3_key_prefix  = var.s3_key_prefix
  sns_topic_arn  = aws_sns_topic.config.arn

  snapshot_delivery_properties {
    delivery_frequency = var.delivery_frequency
  }

  depends_on = [aws_config_configuration_recorder.recorder]
}
```

`aws_config_delivery_channel.bucket` only references `aws_sns_topic.config.arn` and explicitly depends on `aws_config_configuration_recorder.recorder`. It has no implicit or explicit dependency on `aws_sns_topic_policy.config`, which attaches the SNS topic policy granting `config.amazonaws.com` permission (`sns:Publish`) to publish to the topic. Consequently, Terraform can create the delivery channel (and subsequently enable the configuration recorder) before the SNS topic policy is applied.

Correct