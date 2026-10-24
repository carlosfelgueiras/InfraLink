For each reported missing dependency between a node and a target, inspect the Terraform configuration and determine whether the report is correct.

A report is correct if node should depend on target due to a real-world or operational ordering requirement, but this dependency is not currently expressed in the Terraform configuration through either an attribute reference (implicit dependency) or a depends_on declaration (explicit dependency).

In other words, determine whether target must be created, configured, or otherwise made ready before node can be correctly created or operated, and whether Terraform currently lacks the information necessary to enforce that ordering.

Classify each reported dependency as:
Correct — the missing dependency exists as reported.
Incorrect — no such dependency is required, or the required ordering is already expressed in the configuration.

When making the assessment, consider the semantics of the resources and their attributes, provider/API behavior, and any relevant operational requirements. Do not classify a dependency as necessary solely because the two resources are related; there must be a concrete ordering requirement from target to node.

---

## Diagnostic to assess

- Repository: `maddevsio/aws-eks-base`
- Commit: `7a87e5885f2bf76ac1e961b325879aad307755b5`
- Module entrypoint: `terraform/layer2-k8s`
- Source (the resource that should depend on the target): `:resource.helm_release.elk`
- Target (the resource it should depend on): `:resource.kubernetes_secret.elasticsearch_certificates`

Description:

[final-deepseek-v4.1-flash-1017-effort-high-run1]
helm_release.elk references the `elastic-certificates` Secret by name in its chart values, but nothing orders it after kubernetes_secret.elasticsearch_certificates. Elasticsearch/Kibana pods can start before the TLS Secret exists.

----------------------------------------

[final-deepseek-v4.1-flash-1017-effort-high-run2]
`helm_release.elk` mounts the `elastic-certificates` secret (TLS certs for Elasticsearch) by literal name only, so no Terraform edge exists. The release should depend on `kubernetes_secret.elasticsearch_certificates` so the certs exist before the chart's pods start.

----------------------------------------

[final-deepseek-v4.1-flash-1017-effort-high-run3]
`helm_release.elk` mounts the Secret `elastic-certificates` (secretMounts in elasticsearch/kibana/filebeat/apm/metricbeat) by literal name, but does not depend on the `kubernetes_secret.elasticsearch_certificates` that creates it. Pods will fail to start if the Secret is absent, so the release must be ordered after the Secret.

---

## Your environment

- The current working directory is a snapshot of the repository at the commit above. It contains only the file tree, with no git history. The module entrypoint path is relative to this directory.
- Resource addresses are relative to the module entrypoint. `:resource.<type>.<name>` is declared directly in the entrypoint. `module.<call>:resource.<type>.<name>` is declared inside the module that `module "<call>"` instantiates (follow its `source`).
- You can use web search and web fetch for external information, such as provider documentation. Do not look at this repository's history or later versions (commits, pull requests, issues, or other branches after commit `7a87e5885f2bf76ac1e961b325879aad307755b5`).
- End your final message with a single line containing exactly one word, either `Correct` or `Incorrect`.
