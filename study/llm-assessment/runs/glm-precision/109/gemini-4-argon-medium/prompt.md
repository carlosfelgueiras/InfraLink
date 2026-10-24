For each reported missing dependency between a node and a target, inspect the Terraform configuration and determine whether the report is correct.

A report is correct if node should depend on target due to a real-world or operational ordering requirement, but this dependency is not currently expressed in the Terraform configuration through either an attribute reference (implicit dependency) or a depends_on declaration (explicit dependency).

In other words, determine whether target must be created, configured, or otherwise made ready before node can be correctly created or operated, and whether Terraform currently lacks the information necessary to enforce that ordering.

Classify each reported dependency as:
Correct — the missing dependency exists as reported.
Incorrect — no such dependency is required, or the required ordering is already expressed in the configuration.

When making the assessment, consider the semantics of the resources and their attributes, provider/API behavior, and any relevant operational requirements. Do not classify a dependency as necessary solely because the two resources are related; there must be a concrete ordering requirement from target to node.

---

## Diagnostic to assess

- Repository: `cisco-open/forge`
- Commit: `3a9b5f35b4fe41688a454891e9c82f91ea9161b9`
- Module entrypoint: `modules/infra/eks`
- Source (the resource that should depend on the target): `:resource.null_resource.delete_daemonset`
- Target (the resource it should depend on): `:resource.null_resource.create_calico_installation`

Description:

[final-glm-5.3-flash-effort-high-run1]
`null_resource.delete_daemonset` removes the `aws-node` daemonset (disabling the AWS VPC CNI), while `null_resource.create_calico_installation` applies the Calico Installation that takes over pod networking. Both resources depend only on `null_resource.update_kubeconfig`, so Terraform may delete `aws-node` before Calico's Installation exists, leaving pods without pod networking. Calico's standard EKS install order requires deleting `aws-node` only after the Installation is applied. Since both are local-exec kubectl resources, no attribute reference can express this ordering.

----------------------------------------

[final-glm-5.3-flash-effort-high-run2]
null_resource.delete_daemonset runs 'kubectl delete daemonset -n kube-system aws-node' as part of the Calico CNI migration, but it has no dependency on null_resource.create_calico_installation. Nothing in the graph orders the aws-node daemonset deletion after the Calico Installation resource is created; in a single apply these two null_resources can run concurrently, and removing aws-node before Calico is installed can break pod networking. It should depend on null_resource.create_calico_installation (bare depends_on; no data-reference fix is possible for these null_resources).

---

## Your environment

- The current working directory is a snapshot of the repository at the commit above. It contains only the file tree, with no git history. The module entrypoint path is relative to this directory.
- Resource addresses are relative to the module entrypoint. `:resource.<type>.<name>` is declared directly in the entrypoint. `module.<call>:resource.<type>.<name>` is declared inside the module that `module "<call>"` instantiates (follow its `source`).
- You can use web search and web fetch for external information, such as provider documentation. Do not look at this repository's history or later versions (commits, pull requests, issues, or other branches after commit `3a9b5f35b4fe41688a454891e9c82f91ea9161b9`).
- End your final message with a single line containing exactly one word, either `Correct` or `Incorrect`.
