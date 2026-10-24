For each reported missing dependency between a node and a target, inspect the Terraform configuration and determine whether the report is correct.

A report is correct if node should depend on target due to a real-world or operational ordering requirement, but this dependency is not currently expressed in the Terraform configuration through either an attribute reference (implicit dependency) or a depends_on declaration (explicit dependency).

In other words, determine whether target must be created, configured, or otherwise made ready before node can be correctly created or operated, and whether Terraform currently lacks the information necessary to enforce that ordering.

Classify each reported dependency as:
Correct — the missing dependency exists as reported.
Incorrect — no such dependency is required, or the required ordering is already expressed in the configuration.

When making the assessment, consider the semantics of the resources and their attributes, provider/API behavior, and any relevant operational requirements. Do not classify a dependency as necessary solely because the two resources are related; there must be a concrete ordering requirement from target to node.

---

## Diagnostic to assess

- Repository: `github-aws-runners/terraform-aws-github-runner`
- Commit: `fdb4385c6c08d3d7adae70481570b0899d4c9dd9`
- Module entrypoint: `modules/runners`
- Source (the resource that should depend on the target): `:resource.aws_cloudwatch_event_target.ssm_housekeeper`
- Target (the resource it should depend on): `:resource.aws_lambda_permission.ssm_housekeeper`

Description:

[final-deepseek-v4.1-flash-1017-effort-high-run1]
`aws_cloudwatch_event_target.ssm_housekeeper` may be created, and the scheduled rule may fire, before `aws_lambda_permission.ssm_housekeeper` grants EventBridge permission to invoke the function; the target should be ordered after the invoke permission.

----------------------------------------

[final-deepseek-v4.1-flash-1017-effort-high-run2]
aws_cloudwatch_event_target.ssm_housekeeper can invoke aws_lambda_function.ssm_housekeeper only if aws_lambda_permission.ssm_housekeeper (principal events.amazonaws.com) exists first. The target references the rule and the function ARN but not the permission, so EventBridge may register the target before the invoke policy exists, causing scheduled invocations to fail. Add an explicit dependency on aws_lambda_permission.ssm_housekeeper.

----------------------------------------

[final-deepseek-v4.1-flash-1017-effort-high-run3]
aws_cloudwatch_event_target.ssm_housekeeper points the scheduled rule at the ssm_housekeeper Lambda, but it does not depend on aws_lambda_permission.ssm_housekeeper, the resource-based policy that authorizes events.amazonaws.com to invoke the function. Once the rule+target exist (and the rule is ENABLED), an invocation can fire before the Lambda permission is created, causing invocation AccessDenied failures. The event target should be created after the Lambda permission.

---

## Your environment

- The current working directory is a snapshot of the repository at the commit above. It contains only the file tree, with no git history. The module entrypoint path is relative to this directory.
- Resource addresses are relative to the module entrypoint. `:resource.<type>.<name>` is declared directly in the entrypoint. `module.<call>:resource.<type>.<name>` is declared inside the module that `module "<call>"` instantiates (follow its `source`).
- You can use web search and web fetch for external information, such as provider documentation. Do not look at this repository's history or later versions (commits, pull requests, issues, or other branches after commit `fdb4385c6c08d3d7adae70481570b0899d4c9dd9`).
- End your final message with a single line containing exactly one word, either `Correct` or `Incorrect`.
