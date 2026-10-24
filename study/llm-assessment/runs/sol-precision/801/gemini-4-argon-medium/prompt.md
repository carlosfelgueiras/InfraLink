For each reported missing dependency between a node and a target, inspect the Terraform configuration and determine whether the report is correct.

A report is correct if node should depend on target due to a real-world or operational ordering requirement, but this dependency is not currently expressed in the Terraform configuration through either an attribute reference (implicit dependency) or a depends_on declaration (explicit dependency).

In other words, determine whether target must be created, configured, or otherwise made ready before node can be correctly created or operated, and whether Terraform currently lacks the information necessary to enforce that ordering.

Classify each reported dependency as:
Correct — the missing dependency exists as reported.
Incorrect — no such dependency is required, or the required ordering is already expressed in the configuration.

When making the assessment, consider the semantics of the resources and their attributes, provider/API behavior, and any relevant operational requirements. Do not classify a dependency as necessary solely because the two resources are related; there must be a concrete ordering requirement from target to node.

---

## Diagnostic to assess

- Repository: `aws-ia/terraform-aws-eks-blueprints`
- Commit: `c55de99ba5834ebe181d07a38c28838342559329`
- Module entrypoint: `.`
- Source (the resource that should depend on the target): `:data.aws_iam_policy_document.eks_key`
- Target (the resource it should depend on): `:module.aws_eks`

Description:

:data.aws_iam_policy_document.eks_key constructs the cluster IAM-role principal from its expected ARN instead of referencing the role created by :module.aws_eks. Consequently, the KMS key consuming this document can be created before that principal exists, causing KMS to reject the policy as containing an invalid principal. Reference the module's cluster_iam_role_arn output in the principal identifiers to order policy consumption after role creation. Use the role output rather than a broad depends_on on the EKS module, since the cluster itself consumes the KMS key.

---

## Your environment

- The current working directory is a snapshot of the repository at the commit above. It contains only the file tree, with no git history. The module entrypoint path is relative to this directory.
- Resource addresses are relative to the module entrypoint. `:resource.<type>.<name>` is declared directly in the entrypoint. `module.<call>:resource.<type>.<name>` is declared inside the module that `module "<call>"` instantiates (follow its `source`).
- You can use web search and web fetch for external information, such as provider documentation. Do not look at this repository's history or later versions (commits, pull requests, issues, or other branches after commit `c55de99ba5834ebe181d07a38c28838342559329`).
- End your final message with a single line containing exactly one word, either `Correct` or `Incorrect`.
