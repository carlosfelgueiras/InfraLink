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
- Source (the resource that should depend on the target): `module.pool:resource.aws_scheduler_schedule.pool`
- Target (the resource it should depend on): `module.pool:resource.aws_iam_role_policy.scheduler`

Description:

[final-gpt-6-luna-effort-high-run1]
The enabled schedule can invoke the pool Lambda before Scheduler's invocation policy is installed on its execution role. Make the schedule wait for the policy to prevent early invocations from being denied.

----------------------------------------

[final-gpt-6-luna-effort-high-run2]
The scheduled pool Lambda can be invoked before its scheduler role has the policy granting lambda:InvokeFunction. Ensure the role policy is attached before creating the schedule.

----------------------------------------

[final-gpt-6-luna-effort-high-run3]
The EventBridge Scheduler schedule may become active before the scheduler role's Lambda-invoke policy is attached, causing scheduled invocations to be denied. Order schedule creation after the policy resource.

---

## Your environment

- The current working directory is a snapshot of the repository at the commit above. It contains only the file tree, with no git history. The module entrypoint path is relative to this directory.
- Resource addresses are relative to the module entrypoint. `:resource.<type>.<name>` is declared directly in the entrypoint. `module.<call>:resource.<type>.<name>` is declared inside the module that `module "<call>"` instantiates (follow its `source`).
- You can use web search and web fetch for external information, such as provider documentation. Do not look at this repository's history or later versions (commits, pull requests, issues, or other branches after commit `fdb4385c6c08d3d7adae70481570b0899d4c9dd9`).
- End your final message with a single line containing exactly one word, either `Correct` or `Incorrect`.
