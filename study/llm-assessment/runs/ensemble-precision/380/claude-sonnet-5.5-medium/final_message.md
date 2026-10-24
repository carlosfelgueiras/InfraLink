The bucket ID comes from `module.audit_log_bucket`, not from `aws_s3_bucket_policy.audit_log`. Nothing in `module.config_baseline_us-west-2` references the policy, and there is no `depends_on` on it. I checked this in `config_baselines.tf` and `bucket.tf`.

AWS Config checks the bucket policy when `PutDeliveryChannel` is called. If the policy doesn't grant `config.amazonaws.com` write access yet, the call fails with `InsufficientDeliveryPolicyException`. The module's `aws_config_delivery_channel` therefore needs the policy to exist first, but Terraform can't see that ordering.

The two reports describe the failure at different steps: run 1 says it happens when the recorder starts, run 2 says it happens when the delivery channel is created. The delivery channel step is the one that actually validates the policy. Either way, the module needs to wait for the policy.

Correct