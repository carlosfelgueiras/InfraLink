The report is correct. In `modules/fargate-profile/main.tf`, `aws_eks_fargate_profile.this` takes `pod_execution_role_arn` from `aws_iam_role.this[0].arn`. That makes it depend on the role, but not on `aws_iam_role_policy_attachment.this`. The profile has no `depends_on`, and nothing else in its arguments references the attachments.

The ordering requirement is real. Fargate pods need `AmazonEKSFargatePodExecutionRolePolicy` on the role so they can pull images and write logs, and optionally the CNI policy. Pods scheduled onto the profile can fail if those attachments don't exist yet. Without a dependency, Terraform can create the profile in parallel with the attachments. On destroy, it can also remove the attachments before the profile, so pods that are still running lose their permissions.

AWS documentation also says the pod execution role needs the policy attached before the profile is used.

Correct