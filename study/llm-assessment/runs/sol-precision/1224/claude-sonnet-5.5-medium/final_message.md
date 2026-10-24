Terraform doesn't link the target to the permission. The target references only the rule and the function. The permission references the function and the rule.

Does the ordering matter in practice? Creating an EventBridge target for a Lambda function doesn't check permissions. The `PutTargets` call succeeds without them. If the rule fires before the permission exists, the invocation fails. The schedule is periodic, though, and the first firing comes later. The failed invocation is dropped and the next scheduled one succeeds once the permission exists. Nothing breaks permanently. The window is only a few seconds, so this is a harmless race. Terraform's own docs and examples don't add `depends_on` here.

The ordering is weak and has no lasting consequence. It isn't a concrete operational requirement.

Incorrect