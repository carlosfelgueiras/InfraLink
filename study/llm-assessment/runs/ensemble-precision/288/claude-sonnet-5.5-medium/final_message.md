The report is incorrect. EventBridge adds a target and invokes it only when the schedule fires. Terraform's AWS provider doesn't check the permission when it creates the target, so a missing permission would not make creation fail. The rule runs on a schedule, so the chance of a firing landing in the short gap between target creation and permission creation is small. An invocation that fails in that gap is just retried at the next scheduled run. The ordering is not a hard requirement.

In `modules/runner-binaries-syncer/runner-binaries-syncer.tf`, the target depends on the rule and the Lambda function. The permission depends on the same two. The syncer is also triggered separately after deployment, through `aws_s3_object.trigger`.

Incorrect