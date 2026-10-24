## Assessment

**Report: `module.config_baseline_ap-south-1` should depend on `aws_s3_bucket_policy.audit_log` — Correct**

### The ordering requirement is real

`modules/config-baseline/main.tf` creates (in the `ap-south-1` provider):
1. `aws_config_configuration_recorder.recorder` (PutConfigurationRecorder)
2. `aws_config_delivery_channel.bucket` (PutDeliveryChannel) — pointed at the audit log bucket
3. `aws_config_configuration_recorder_status.recorder` (StartConfigurationRecorder)

The delivery channel's `s3_bucket_name` points at the audit log bucket, which is created by `module.audit_log_bucket` (`modules/secure-bucket`) with a private ACL, public access block, and **no bucket policy**. The *only* thing granting `config.amazonaws.com` the required `s3:PutObject`/`s3:GetBucketAcl` access is `resource.aws_s3_bucket_policy.audit_log` (bucket.tf:119, statements `AWSCloudTrailAclCheckForConfig` / `AWSCloudTrailWriteForConfig`).

AWS documents this as a hard service-side check: `PutDeliveryChannel` (what `aws_config_delivery_channel` calls) throws **`InsufficientDeliveryPolicyException` — "Your Amazon S3 bucket policy does not allow AWS Config to write to it"** — and `StartConfigurationRecorder` (what `aws_config_configuration_recorder_status` calls) requires a valid delivery channel. So the bucket policy must be applied **before** the delivery channel is created and the recorder is started, exactly as both runs describe.

### The dependency is not currently expressed

- `module.config_baseline_ap-south-1` implicitly depends only on `aws_iam_role.recorder` (via `iam_role_arn`) and `module.audit_log_bucket` (via `s3_bucket_name = local.audit_log_bucket_id` → `module.audit_log_bucket.this_bucket.id`). The bucket name is a plain string and carries no reference to the policy.
- `aws_s3_bucket_policy.audit_log` also depends only on `module.audit_log_bucket` and `data.aws_iam_policy_document.audit_log[0]`.
- There is no `depends_on` on the module, no reference to the policy resource, and no transitive path connecting them. In the Terraform graph they are siblings: Terraform may apply the recorder/delivery channel (and start the recorder) **before** the bucket policy, causing a fresh-apply failure with `InsufficientDeliveryPolicyException` (both PutDeliveryChannel and Start would fail).

Both diagnostic runs correctly identify this missing dependency (whether the failure surfaces at delivery-channel creation or at recorder start, the requirement and the fix — `depends_on = [aws_s3_bucket_policy.audit_log[0]]` on the module — are the same).

Correct