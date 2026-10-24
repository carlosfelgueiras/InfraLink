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
- Commit: `a07e7c3783b0622c539c6c7633b35c5b57b58a4f`
- Module entrypoint: `modules/infra/eks`
- Source (the resource that should depend on the target): `:resource.null_resource.delete_daemonset`
- Target (the resource it should depend on): `:resource.null_resource.create_calico_installation`

Description:

[final-deepseek-v4.1-flash-1017-effort-high-run1]
`:resource.null_resource.delete_daemonset` removes the AWS VPC CNI `aws-node` DaemonSet, which must only happen once Calico has been installed and is providing pod networking. It currently depends only on `null_resource.update_kubeconfig`/`module.eks`, so nothing orders it after `:resource.null_resource.create_calico_installation`; Terraform may delete `aws-node` before the Calico `Installation` exists, leaving the cluster without a working CNI. Add an explicit `depends_on = [null_resource.create_calico_installation]` (there is no clean attribute reference on a `null_resource` to express this).

----------------------------------------

[final-deepseek-v4.1-flash-1017-effort-high-run2]
null_resource.delete_daemonset deletes the aws-node (VPC CNI) DaemonSet, which should only happen once Calico has been installed so a new CNI is in place. It currently depends only on module.eks and null_resource.update_kubeconfig, so nothing guarantees null_resource.create_calico_installation has run first — deleting the CNI beforehand leaves nodes without pod networking. Add a dependency on null_resource.create_calico_installation.

----------------------------------------

[final-deepseek-v4.1-flash-1017-effort-high-run3]
null_resource.delete_daemonset deletes the aws-node (VPC CNI) daemonset, but it only depends on module.eks and null_resource.update_kubeconfig. It must be ordered after null_resource.create_calico_installation so the Calico CNI Installation exists before the previous CNI is torn down; otherwise nodes are left with no working network plugin and pods scheduled by later steps (Karpenter, node pools) will fail. No attribute of a null_resource gives a clean data reference, so an explicit depends_on = [null_resource.create_calico_installation] is the appropriate fix.

---

## Your environment

- The current working directory is a snapshot of the repository at the commit above. It contains only the file tree, with no git history. The module entrypoint path is relative to this directory.
- Resource addresses are relative to the module entrypoint. `:resource.<type>.<name>` is declared directly in the entrypoint. `module.<call>:resource.<type>.<name>` is declared inside the module that `module "<call>"` instantiates (follow its `source`).
- You can use web search and web fetch for external information, such as provider documentation. Do not look at this repository's history or later versions (commits, pull requests, issues, or other branches after commit `a07e7c3783b0622c539c6c7633b35c5b57b58a4f`).
- End your final message with a single line containing exactly one word, either `Correct` or `Incorrect`.
