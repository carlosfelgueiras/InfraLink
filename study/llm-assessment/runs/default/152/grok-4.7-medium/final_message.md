`helm_release.elk` mounts the Secret `elastic-certificates` by a literal name in its chart values (`secretMounts` for Elasticsearch and Kibana, and the equivalent volume mounts for Filebeat). Those values do not interpolate any attribute of `kubernetes_secret.elasticsearch_certificates`, and the release has no `depends_on`.

The Elasticsearch 7.16 chart turns that name into a Secret volume. With TLS enabled and the certificate paths pointing at that mount, the kubelet will not start the pods until the Secret exists. The Helm provider's `wait` defaults to true, and this release sets a 900-second timeout, so Terraform marks the release successful only after those pods are ready. The Secret must therefore exist first, and Terraform currently has no edge that enforces that order.

Correct