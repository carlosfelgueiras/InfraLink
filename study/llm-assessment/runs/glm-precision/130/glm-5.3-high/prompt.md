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
- Module entrypoint: `modules/ami-housekeeper`
- Source (the resource that should depend on the target): `:resource.aws_lambda_function.ami_housekeeper`
- Target (the resource it should depend on): `:resource.aws_cloudwatch_log_group.ami_housekeeper`

Description:

[final-glm-5.3-flash-effort-high-run1]
aws_cloudwatch_log_group.ami_housekeeper currently depends on aws_lambda_function.ami_housekeeper (its name references aws_lambda_function.ami_housekeeper.function_name), so the function is created first and the managed log group afterwards. If the function is invoked in that window (it is wired to a scheduled EventBridge rule), Lambda auto-creates /aws/lambda/<name> with default settings, which then collides with this resource ("The specified log group already exists"). The documented pattern is to pre-create the log group and add a bare depends_on on the function. Note: adding that depends_on requires first decoupling the log group's name from the function — e.g. name = "/aws/lambda/${var.prefix}-ami-housekeeper", which matches function_name = "${var.prefix}-ami-housekeeper" — otherwise a cycle would result.

----------------------------------------

[final-glm-5.3-flash-effort-high-run2]
aws_lambda_function.ami_housekeeper does not depend on aws_cloudwatch_log_group.ami_housekeeper, but the log group must exist before the function is invoked: if Lambda is invoked while the Terraform-managed log group is absent, the Lambda service auto-creates a default /aws/lambda/<function_name> log group (no retention policy, default encryption, STANDARD class), and the subsequent create of aws_cloudwatch_log_group.ami_housekeeper then fails with ResourceAlreadyExistsException — so the intended retention_in_days, kms_key_id, and log_group_class settings are never applied. The current graph only has the reverse edge (the log group's name references aws_lambda_function.ami_housekeeper.function_name), which forces the function to be created first. A bare depends_on on the function would create a cycle with that name reference; the recommended fix is to compute the function name in a local (e.g. local.function_name = "${var.prefix}-ami-housekeeper"), use it for both the function_name and the log group name, and add depends_on = [aws_cloudwatch_log_group.ami_housekeeper] to the lambda function.

----------------------------------------

[final-glm-5.3-flash-effort-high-run3]
aws_lambda_function.ami_housekeeper is created before aws_cloudwatch_log_group.ami_housekeeper (the log group references the function's name, inverting the required order). Lambda auto-creates a default log group (no retention, no KMS) on first log write, so an invocation arriving before the log group is provisioned either yields a log group with the wrong settings or makes the log group's own create fail with ResourceAlreadyExistsException. The function must be ordered after the log group; since the log group currently references the function's name (which would create a cycle), the name should be computed directly (e.g. "/aws/lambda/${var.prefix}-ami-housekeeper") and the function given a bare depends_on on the log group.

---

## Your environment

- The current working directory is a snapshot of the repository at the commit above. It contains only the file tree, with no git history. The module entrypoint path is relative to this directory.
- Resource addresses are relative to the module entrypoint. `:resource.<type>.<name>` is declared directly in the entrypoint. `module.<call>:resource.<type>.<name>` is declared inside the module that `module "<call>"` instantiates (follow its `source`).
- You can use web search and web fetch for external information, such as provider documentation. Do not look at this repository's history or later versions (commits, pull requests, issues, or other branches after commit `fdb4385c6c08d3d7adae70481570b0899d4c9dd9`).
- End your final message with a single line containing exactly one word, either `Correct` or `Incorrect`.
