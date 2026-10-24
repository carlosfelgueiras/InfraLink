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
- Source (the resource that should depend on the target): `:resource.aws_lambda_function.scale_up`
- Target (the resource it should depend on): `module.job_retry:output.job_retry_check_queue`

Description:

[merged-glm-5.3-flash-atleast2of3]
[final-glm-5.3-flash-effort-high-run1]
The scale-up lambda embeds the job-retry check queue URL in its environment: `JOB_RETRY_CONFIG = jsonencode(local.job_retry_config)` where `local.job_retry_config` reads `module.job_retry[0].job_retry_check_queue.url`. The dependency graph shows no edge from :resource.aws_lambda_function.scale_up to module.job_retry:output.job_retry_check_queue (the reference is hidden behind a local), so the function could be created before the job-retry queue exists and would not be updated when the queue URL changes. Add `depends_on = [module.job_retry]` (or otherwise surface the queue reference in a direct attribute) on the scale-up lambda.

----------------------------------------

[final-glm-5.3-flash-effort-high-run3]
`:resource.aws_lambda_function.scale_up` sets the `JOB_RETRY_CONFIG` environment variable from `local.job_retry_config`, which embeds `module.job_retry[0].job_retry_check_queue.url`, but the function has no dependency on `module.job_retry:output.job_retry_check_queue` (only the sibling `aws_iam_role_policy.job_retry_sqs_publish` depends on it). The scale-up function can therefore be created before the job-retry check queue exists, pointing at a queue URL that is not yet provisioned.

---

## Your environment

- The current working directory is a snapshot of the repository at the commit above. It contains only the file tree, with no git history. The module entrypoint path is relative to this directory.
- Resource addresses are relative to the module entrypoint. `:resource.<type>.<name>` is declared directly in the entrypoint. `module.<call>:resource.<type>.<name>` is declared inside the module that `module "<call>"` instantiates (follow its `source`).
- You can use web search and web fetch for external information, such as provider documentation. Do not look at this repository's history or later versions (commits, pull requests, issues, or other branches after commit `fdb4385c6c08d3d7adae70481570b0899d4c9dd9`).
- End your final message with a single line containing exactly one word, either `Correct` or `Incorrect`.
