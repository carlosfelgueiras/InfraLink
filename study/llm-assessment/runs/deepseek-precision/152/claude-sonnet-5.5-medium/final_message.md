The report is correct. Terraform has no edge from `helm_release.elk` to `kubernetes_secret.elasticsearch_certificates`.

- **No dependency declared:** `helm_release.elk` in `terraform/layer2-k8s/eks-elk.tf` has no `depends_on`.
- **Literal name only:** The chart values refer to the Secret as the literal string `elastic-certificates` (`secretName: elastic-certificates` in the Elasticsearch, Kibana and beats values). The values don't reference `kubernetes_secret.elasticsearch_certificates.metadata[0].name`, so there is no implicit dependency either.
- **Real ordering need:** The pods mount that Secret, so it has to exist before they can start. The two resources share only the namespace, which orders neither one after the other.

Since the chart values don't depend on the Secret, Terraform could create the release first. Any pod that tried to mount the missing Secret would fail until the Secret appeared. With the 900-second timeout, the release could end up failing.

Correct