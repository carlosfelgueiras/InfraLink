The report is not correct. The props stanza `props/kube:container:runner` lists the transform name `forgecicd_kube_container_runner_ci_result` as a plain string in a `REPORT-...` entry (`props_k8s.tf`, line 6). It has no attribute reference to the transform resource, so Terraform does not see a dependency. That part of the report is accurate.

The ordering is still not a real requirement, for two reasons:

- **Splunk does not validate the reference.** The configs endpoint stores props values as plain text. It accepts a `REPORT-` entry that names a transform that doesn't exist yet, and creating the props stanza does not fail.
- **The only effect is a transient search-time error.** Splunk resolves the transform name when it reads the configuration or runs a search. If the transform is missing for a moment, the field extraction simply doesn't apply. It resolves itself once the transform exists, and nothing needs to be re-applied.

The props stanza therefore does not need the transform to exist first. I judged this from the Splunk behavior above and did not check the provider's source.

Incorrect