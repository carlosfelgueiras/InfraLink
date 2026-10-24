For each reported missing dependency between a node and a target, inspect the Terraform configuration and determine whether the report is correct.

A report is correct if node should depend on target due to a real-world or operational ordering requirement, but this dependency is not currently expressed in the Terraform configuration through either an attribute reference (implicit dependency) or a depends_on declaration (explicit dependency).

In other words, determine whether target must be created, configured, or otherwise made ready before node can be correctly created or operated, and whether Terraform currently lacks the information necessary to enforce that ordering.

Classify each reported dependency as:
Correct — the missing dependency exists as reported.
Incorrect — no such dependency is required, or the required ordering is already expressed in the configuration.

When making the assessment, consider the semantics of the resources and their attributes, provider/API behavior, and any relevant operational requirements. Do not classify a dependency as necessary solely because the two resources are related; there must be a concrete ordering requirement from target to node.

---

## Diagnostic to assess

- Repository: `BigDataBoutique/elasticsearch-cloud-deploy`
- Commit: `2e2c83a7bedaa4066e9e722919c34ef7fe65ac50`
- Module entrypoint: `terraform-aws`
- Source (the resource that should depend on the target): `:resource.aws_instance.bootstrap_node`
- Target (the resource it should depend on): `:resource.aws_iam_role_policy.elasticsearch`

Description:

[final-gpt-6-luna-effort-high-run1]
The bootstrap EC2 instance can start before the Elasticsearch role's inline discovery policy is attached. Order instance creation after the policy so its bootstrap code has the required EC2 describe permissions.

----------------------------------------

[final-gpt-6-luna-effort-high-run2]
The bootstrap EC2 instance uses the Elasticsearch discovery role and can start its bootstrap process before the discovery policy is attached. Add an explicit dependency so the instance is created after the policy is provisioned.

---

## Your environment

- The current working directory is a snapshot of the repository at the commit above. It contains only the file tree, with no git history. The module entrypoint path is relative to this directory.
- Resource addresses are relative to the module entrypoint. `:resource.<type>.<name>` is declared directly in the entrypoint. `module.<call>:resource.<type>.<name>` is declared inside the module that `module "<call>"` instantiates (follow its `source`).
- You can use web search and web fetch for external information, such as provider documentation. Do not look at this repository's history or later versions (commits, pull requests, issues, or other branches after commit `2e2c83a7bedaa4066e9e722919c34ef7fe65ac50`).
- End your final message with a single line containing exactly one word, either `Correct` or `Incorrect`.
