# Assessment

## The reported dependency

`module.config_baseline_us-west-1` (instantiating `./modules/config-baseline` against the `aws.us-west-1` provider) should depend on `aws_s3_bucket_policy.audit_log` (root `bucket.tf`).

## 1. A concrete ordering requirement exists

The module creates, in order: `aws_config_configuration_recorder.recorder` → `aws_config_delivery_channel.bucket` (→ `PutDeliveryChannel`) → `aws_config_configuration_recorder_status.recorder` (→ `StartConfigurationRecorder`), with the delivery channel targeting the audit-log bucket (`s3_bucket_name` ← `local.audit_log_bucket_id`).

- The AWS Config API Reference documents **`InsufficientDeliveryPolicyException` — "Your Amazon S3 bucket policy does not allow AWS Config to write to it"** as an error of **`PutDeliveryChannel`**: the delivery-channel creation itself synchronously validates that Config can write to the target bucket. (`StartConfigurationRecorder`'s documented errors do not include this exception — so run 2's description of the failure point is the accurate one; run 1 mislocates it slightly, but the delivery channel is created inside the same module before the recorder status.)
- Real-world confirmation: hashicorp/terraform-provider-aws issues #8655 and #17898 both show `Creating Delivery Channel failed: InsufficientDeliveryPolicyException: Insufficient delivery policy to s3 bucket: ..., unable to write to bucket` when the delivery channel is created before the bucket policy is in place.
- The AWS Config Developer Guide requires a bucket policy granting `config.amazonaws.com` `s3:GetBucketAcl`/`s3:PutObject` — exactly the `AWSCloudTrailAclCheckForConfig`/`AWSCloudTrailWriteForConfig` statements that `aws_s3_bucket_policy.audit_log` attaches.

So the bucket policy must be applied before the module's delivery channel can be created and the recorder started.

## 2. The dependency is not expressed in Terraform

- `s3_bucket_name = local.audit_log_bucket_id` (`config_baselines.tf:331`) is a plain string that creates only an **implicit dependency on the S3 bucket** (`module.audit_log_bucket.this_bucket.id`), not on the bucket policy.
- The module's `depends_on` blocks only order its own internal resources; neither the module block nor `modules/config-baseline/main.tf` references `aws_s3_bucket_policy.audit_log` in any way (verified by inspection and grep).
- No transitive path exists: the recorder IAM role/policies referenced by the module depend only on the bucket ARN, and the secure-bucket module's outputs expose only the bucket objects, never the policy.
- Consequently, on a fresh apply both `aws_s3_bucket_policy.audit_log` and the module's `aws_config_delivery_channel` become eligible concurrently after the bucket is created; Terraform may apply the delivery channel first, causing `PutDeliveryChannel` to fail with `InsufficientDeliveryPolicyException` (a known flaky failure mode of this module). The `use_external_audit_log_bucket` case removes the policy (`count = 0`), but in the default configuration the policy exists and the ordering is required.

## Verdict

The bucket policy must be in place before the module's delivery channel/recorder-status resources can be created, and Terraform currently has no way to enforce that ordering. The report is correct.

Correct