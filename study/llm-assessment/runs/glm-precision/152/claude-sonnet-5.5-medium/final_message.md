The report is incorrect. Here is why.

The addon only reads the role ARN. The collector pods get their credentials later, when they run and assume the role through IRSA. If the policy attachments land a few seconds after the addon is created, the pods only hit authorization errors if they make AWS calls in that gap. IAM changes also propagate eventually. The AWS SDKs retry, and the addon creation does not validate the permissions. The ordering is therefore a soft convenience, not a hard requirement.

Terraform does not enforce this ordering. The addon references `aws_iam_role.adot_collector.arn`, and nothing links it to the attachments resource. But the attachments don't have to exist before the addon can be created or work correctly, so no dependency is missing.

Incorrect