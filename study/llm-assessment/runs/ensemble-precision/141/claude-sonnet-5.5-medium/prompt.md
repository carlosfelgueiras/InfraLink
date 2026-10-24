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
- Module entrypoint: `examples/runner-docker`
- Source (the resource that should depend on the target): `module.runner:resource.aws_launch_configuration.gitlab_runner_instance`
- Target (the resource it should depend on): `module.runner:resource.aws_iam_role_policy_attachment.ssm`

Description:

[merged-deepseek-v4.1-flash-1017-atleast2of3]
[final-deepseek-v4.1-flash-1017-effort-high-run1]
The runner's user_data accesses SSM (get/put the runner token) when enable_manage_gitlab_token is true, which requires the SSM access policy to be attached to the instance role. aws_iam_role_policy_attachment.ssm attaches to aws_iam_role.instance in parallel with the instance profile, and the launch configuration waits only on the profile, so an instance can boot before the SSM policy is attached. The launch configuration should depend on the ssm policy attachment.

----------------------------------------

[final-deepseek-v4.1-flash-1017-effort-high-run3]
The runner agent reads/writes the GitLab registration token in SSM, requiring the permissions from aws_iam_policy.ssm. The attachment is not ordered before the instance, so registration can fail if the policy is not yet attached. Order the launch configuration after aws_iam_role_policy_attachment.ssm.

---

## Your environment

- The current working directory is a snapshot of the repository at the commit above. It contains only the file tree, with no git history. The module entrypoint path is relative to this directory.
- Resource addresses are relative to the module entrypoint. `:resource.<type>.<name>` is declared directly in the entrypoint. `module.<call>:resource.<type>.<name>` is declared inside the module that `module "<call>"` instantiates (follow its `source`).
- You can use web search and web fetch for external information, such as provider documentation. Do not look at this repository's history or later versions (commits, pull requests, issues, or other branches after commit `c1287813406a930e2c6d5a5a2caf938cb198496c`).
- End your final message with a single line containing exactly one word, either `Correct` or `Incorrect`.
