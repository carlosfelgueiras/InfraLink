In `terraform/layer2-k8s/eks-elk.tf`, `resource "kubernetes_secret" "elasticsearch_certificates"` creates the Kubernetes Secret named `elastic-certificates` in the ELK namespace containing the TLS certificate and private key (`tls.crt`, `tls.key`, `tls.p8`).

`resource "helm_release" "elk"` deploys the ELK chart (Elasticsearch, Kibana, Filebeat, etc.) in the same namespace. Its Helm values (`local.elk_elasticsearch_values`, `local.elk_kibana_values`, `local.elk_filebeat_values`, `local.elk_apm_values`, and `local.elk_metricbeat_values`) configure volume mounts referencing the secret by the hardcoded literal string `elastic-certificates` rather than referencing an attribute of `kubernetes_secret.elasticsearch_certificates`, and `helm_release.elk` has no `depends_on` declaration.

Because `helm_release.elk` requires the `elastic-certificates` Secret to exist for its pods to mount the TLS certificates and start up (and for Helm's readiness wait to succeed), `helm_release.elk` must depend on `kubernetes_secret.elasticsearch_certificates`.

Correct