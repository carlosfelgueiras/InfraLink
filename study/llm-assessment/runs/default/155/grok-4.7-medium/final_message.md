`aws_cloudtrail.main` only waits on the bucket, not the bucket policy, and CloudTrail rejects trail creation until that policy is attached.

In `terraform/layer1-aws/aws-cloudtrail.tf`, `aws_cloudtrail.main` sets `s3_bucket_name = aws_s3_bucket.cloudtrail.id` and has no `depends_on`. `aws_s3_bucket_policy.cloudtrail` is a separate resource (provider `4.10.0`) that also only references the bucket. Terraform can therefore create the trail and the policy at the same time after the bucket exists.

`CreateTrail` checks the bucket policy immediately and returns `InsufficientS3BucketPolicyException` if `cloudtrail.amazonaws.com` does not already have `s3:GetBucketAcl` and `s3:PutObject`. A new bucket has no such policy until `aws_s3_bucket_policy.cloudtrail` is applied. The policy resource exports nothing the trail can reference, so the ordering is not implied and must be an explicit `depends_on`.

Correct