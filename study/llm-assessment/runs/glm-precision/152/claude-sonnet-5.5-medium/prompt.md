For each reported missing dependency between a node and a target, inspect the Terraform configuration and determine whether the report is correct.

A report is correct if node should depend on target due to a real-world or operational ordering requirement, but this dependency is not currently expressed in the Terraform configuration through either an attribute reference (implicit dependency) or a depends_on declaration (explicit dependency).

In other words, determine whether target must be created, configured, or otherwise made ready before node can be correctly created or operated, and whether Terraform currently lacks the information necessary to enforce that ordering.

Classify each reported dependency as:
Correct — the missing dependency exists as reported.
Incorrect — no such dependency is required, or the required ordering is already expressed in the configuration.

When making the assessment, consider the semantics of the resources and their attributes, provider/API behavior, and any relevant operational requirements. Do not classify a dependency as necessary solely because the two resources are related; there must be a concrete ordering requirement from target to node.

---

## Diagnostic to assess

- Repository: `marcincuber/eks`
- Commit: `e5f8996c7d6a4732743f5eb24ad297ed9f7c6bf5`
- Module entrypoint: `terraform`
- Source (the resource that should depend on the target): `:resource.aws_eks_addon.adot`
- Target (the resource it should depend on): `:resource.aws_iam_role_policy_attachments_exclusive.adot_collector`

Description:

[final-glm-5.3-flash-effort-high-run1]
:resource.aws_eks_addon.adot references :resource.aws_iam_role.adot_collector via service_account_role_arn but not its policy attachments; if :resource.aws_iam_role_policy_attachments_exclusive.adot_collector applies after the addon, the ADOT collector cannot write to Prometheus/X-Ray/CloudWatch.

----------------------------------------

[final-glm-5.3-flash-effort-high-run3]
aws_eks_addon.adot sets service_account_role_arn from aws_iam_role.adot_collector.arn but does not depend on aws_iam_role_policy_attachments_exclusive.adot_collector. The addon provider docs require the service-account role to already have the IAM permissions the addon needs; if the addon is applied before the Prometheus/X-Ray/CloudWatch policy attachments, the collector pods fail authorization.

---

## Your environment

- The current working directory is a snapshot of the repository at the commit above. It contains only the file tree, with no git history. The module entrypoint path is relative to this directory.
- Resource addresses are relative to the module entrypoint. `:resource.<type>.<name>` is declared directly in the entrypoint. `module.<call>:resource.<type>.<name>` is declared inside the module that `module "<call>"` instantiates (follow its `source`).
- You can use web search and web fetch for external information, such as provider documentation. Do not look at this repository's history or later versions (commits, pull requests, issues, or other branches after commit `e5f8996c7d6a4732743f5eb24ad297ed9f7c6bf5`).
- End your final message with a single line containing exactly one word, either `Correct` or `Incorrect`.
