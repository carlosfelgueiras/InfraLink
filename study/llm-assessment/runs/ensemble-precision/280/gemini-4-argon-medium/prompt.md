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
- Commit: `1b243426fdb76fc9fff2d244df357f15bbbb7b24`
- Module entrypoint: `examples/ubuntu`
- Source (the resource that should depend on the target): `module.runners.module.runners:resource.aws_cloudwatch_event_target.scale_down`
- Target (the resource it should depend on): `module.runners.module.runners:resource.aws_lambda_permission.scale_down`

Description:

[merged-gpt-6-luna-atleast2of3]
[final-gpt-6-luna-effort-high-run1]
`module.runners.module.runners:resource.aws_cloudwatch_event_target.scale_down` targets the scale-down Lambda but does not wait for its EventBridge invoke permission. Add an ordering dependency so a scheduled event cannot be delivered before invocation is authorized.

----------------------------------------

[final-gpt-6-luna-effort-high-run2]
`module.runners.module.runners:resource.aws_cloudwatch_event_target.scale_down` can become active before EventBridge has permission to invoke the scale-down Lambda; an event arriving in that interval can fail. Wait for the corresponding Lambda permission.

----------------------------------------

[final-gpt-6-luna-effort-high-run3]
EventBridge can invoke the scale-down Lambda, but this target has no ordering dependency on the permission granting EventBridge access. Ensure the permission exists before registering the target.

---

## Your environment

- The current working directory is a snapshot of the repository at the commit above. It contains only the file tree, with no git history. The module entrypoint path is relative to this directory.
- Resource addresses are relative to the module entrypoint. `:resource.<type>.<name>` is declared directly in the entrypoint. `module.<call>:resource.<type>.<name>` is declared inside the module that `module "<call>"` instantiates (follow its `source`).
- You can use web search and web fetch for external information, such as provider documentation. Do not look at this repository's history or later versions (commits, pull requests, issues, or other branches after commit `1b243426fdb76fc9fff2d244df357f15bbbb7b24`).
- End your final message with a single line containing exactly one word, either `Correct` or `Incorrect`.
