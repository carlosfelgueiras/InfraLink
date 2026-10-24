For each reported missing dependency between a node and a target, inspect the Terraform configuration and determine whether the report is correct.

A report is correct if node should depend on target due to a real-world or operational ordering requirement, but this dependency is not currently expressed in the Terraform configuration through either an attribute reference (implicit dependency) or a depends_on declaration (explicit dependency).

In other words, determine whether target must be created, configured, or otherwise made ready before node can be correctly created or operated, and whether Terraform currently lacks the information necessary to enforce that ordering.

Classify each reported dependency as:
Correct — the missing dependency exists as reported.
Incorrect — no such dependency is required, or the required ordering is already expressed in the configuration.

When making the assessment, consider the semantics of the resources and their attributes, provider/API behavior, and any relevant operational requirements. Do not classify a dependency as necessary solely because the two resources are related; there must be a concrete ordering requirement from target to node.

---

## Diagnostic to assess

- Repository: `cattle-ops/terraform-aws-gitlab-runner`
- Commit: `c1287813406a930e2c6d5a5a2caf938cb198496c`
- Module entrypoint: `examples/runner-public`
- Source (the resource that should depend on the target): `module.runner:data.template_file.gitlab_runner`
- Target (the resource it should depend on): `module.runner:resource.aws_ssm_parameter.runner_registration_token`

Description:

module.runner:data.template_file.gitlab_runner passes the SSM token parameter name through a local string, without depending on module.runner:resource.aws_ssm_parameter.runner_registration_token. The ASG can therefore boot and let user-data read or write the token before Terraform initializes the parameter to "null", causing a missing-parameter or competing-creation race. Use the managed parameter's name in the template variables to order the launch transitively.

---

## Your environment

- The current working directory is a snapshot of the repository at the commit above. It contains only the file tree, with no git history. The module entrypoint path is relative to this directory.
- Resource addresses are relative to the module entrypoint. `:resource.<type>.<name>` is declared directly in the entrypoint. `module.<call>:resource.<type>.<name>` is declared inside the module that `module "<call>"` instantiates (follow its `source`).
- You can use web search and web fetch for external information, such as provider documentation. Do not look at this repository's history or later versions (commits, pull requests, issues, or other branches after commit `c1287813406a930e2c6d5a5a2caf938cb198496c`).
- End your final message with a single line containing exactly one word, either `Correct` or `Incorrect`.
