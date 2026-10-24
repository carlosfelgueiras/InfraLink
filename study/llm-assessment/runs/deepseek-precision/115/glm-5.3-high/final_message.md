## Assessment

**Configuration facts** (from `modules/integrations/splunk_aws_billing`):

- `aws_bcmdataexports_export.cur_per_service` (`billing_per_service.tf`, lines 67–110) references only `aws_s3_bucket.aws_billing_report.id` in its `s3_destination` block, plus `var.aws_region`. It has **no attribute reference** to `aws_s3_bucket_policy.cur_bucket_policy` and **no `depends_on`** declaration.
- The bucket policy (`s3.tf`, lines 125–128) is a separate resource attaching the `cur_bucket_policy` IAM document, whose `EnableAWSDataExportsToWriteToS3AndCheckPolicy` statement grants `bcm-data-exports.amazonaws.com` `s3:PutObject` and `s3:GetBucketPolicy` on the bucket.
- Nothing else in the module introduces an ordering edge between the export and the bucket policy (grep confirms no other references).

**Ordering requirement:**

1. **Create-time:** The AWS Data Exports service validates write access to the destination bucket when the export is created. AWS documentation states the bucket policy "must be applied to every S3 bucket ... when creating a data export," and the `s3:GetBucketPolicy` permission in the policy exists precisely so the service can verify the policy. Community-documented evidence confirms the concrete failure mode: `ValidationException: S3 bucket permission validation failed` when the policy granting the export service principals write access is missing.
2. **Operate-time:** Even absent create-time validation, the export's data deliveries (`s3:PutObject` by `bcm-data-exports.amazonaws.com`, subject to the `aws:SourceArn`/`aws:SourceAccount` conditions in the policy) would fail without the policy attached — "editing the bucket policy ... after you've created an export may prevent Data Exports from delivering your exports."

**Terraform's current knowledge:** Because the bucket and the bucket policy are separate resources, and the export references only the bucket, Terraform can (and on a fresh apply may) create the export before attaching the bucket policy. The required ordering — bucket policy before export — is not expressed anywhere in the configuration.

This is a concrete operational ordering requirement, not merely a relationship between related resources, and Terraform currently lacks the edge to enforce it.

Correct