In `terraform/layer2-k8s/eks-elk.tf`, `resource "helm_release" "elk"` deploys the ELK stack (Elasticsearch, Kibana, Filebeat, APM Server, and Metricbeat) with hardcoded volume/secret mount references to the Kubernetes Secret named `elastic-certificates`:

- `local.elk_elasticsearch_values` (lines 69–72) mounts `secretName: elastic-certificates` for Elasticsearch TLS certificates (`tls.crt` and `tls.key`).
- `local.elk_kibana_values` (lines 145–148) mounts `secretName: elastic-certificates` for Kibana TLS configuration.
- `local.elk_filebeat_values` (lines 384–387), `local.elk_apm_values` (lines 433–436), and `local.elk_metricbeat_values` (lines 536–539, 581–584) similarly mount `secretName: elastic-certificates`.

The `elastic-certificates` Secret is created by `resource "kubernetes_secret" "elasticsearch_certificates"` (lines 735–748). Because `helm_release.elk` references the secret name as a literal string rather than via `kubernetes_secret.elasticsearch_certificates` attributes and has no `depends_on` block, Terraform can install the Helm release before the secret exists, causing pods to fail volume mounting (`ContainerCreating`) or readiness checks.

Correct