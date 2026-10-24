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

[final-glm-5.3-flash-effort-high-run1]
:resource.helm_release.elk mounts the `elastic-certificates` Secret (TLS key/cert) via secretMounts into Elasticsearch, Kibana, Filebeat, APM and Metricbeat containers. That Secret is created by :resource.kubernetes_secret.elasticsearch_certificates, but the release has no dependency on it, so pods can come up before the certificates exist. This ordering is not captured by any attribute reference or depends_on.

----------------------------------------

[final-glm-5.3-flash-effort-high-run2]
helm_release.elk mounts secret "elastic-certificates" into Elasticsearch, Kibana, Filebeat and APM pods (secretMounts / TLS config), but has no dependency on kubernetes_secret.elasticsearch_certificates.

----------------------------------------

[final-glm-5.3-flash-effort-high-run3]
:resource.helm_release.elk mounts the secret "elastic-certificates" (secretMounts for TLS certs) referenced by name in its values, but has no dependency on :resource.kubernetes_secret.elasticsearch_certificates. Without ordering, Elasticsearch/Kibana/filebeat pods can start before the TLS certificates secret exists and crash. Add an explicit depends_on for this secret.

---

## Your environment

- The current working directory is a snapshot of the repository at the commit above. It contains only the file tree, with no git history. The module entrypoint path is relative to this directory.
- Resource addresses are relative to the module entrypoint. `:resource.<type>.<name>` is declared directly in the entrypoint. `module.<call>:resource.<type>.<name>` is declared inside the module that `module "<call>"` instantiates (follow its `source`).
- You can use web search and web fetch for external information, such as provider documentation. Do not look at this repository's history or later versions (commits, pull requests, issues, or other branches after commit `7a87e5885f2bf76ac1e961b325879aad307755b5`).
- End your final message with a single line containing exactly one word, either `Correct` or `Incorrect`.
