In `terraform/layer2-k8s/eks-elk.tf`:

- `kubernetes_secret.elasticsearch_credentials` (lines 721–733) creates the Kubernetes Secret named `elastic-credentials` in `module.elk_namespace[count.index].name`.
- `helm_release.elk` (lines 836–855) installs the ELK Helm chart into the same namespace using values (`local.elk_elasticsearch_values`, `local.elk_kibana_values`, `local.elk_filebeat_values`, `local.elk_apm_values`, and `local.elk_metricbeat_values`) that reference the secret by the hardcoded string `elastic-credentials` via `secretKeyRef` (e.g., lines 60–67, 118–125, 183–190, 392–399).
- Because `helm_release.elk` neither references any attribute of `kubernetes_secret.elasticsearch_credentials` nor declares `depends_on`, Terraform can install the Helm release before the `elastic-credentials` Secret exists, causing pods and init containers in the release to fail with `CreateContainerConfigError` (and potentially causing `helm_release.elk` to fail waiting for readiness).

Correct