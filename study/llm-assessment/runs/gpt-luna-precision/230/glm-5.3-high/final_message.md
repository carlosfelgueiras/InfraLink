## Assessment

**Configuration under review** (`terraform/layer2-k8s/eks-elk.tf`):

1. **`kubernetes_secret.elasticsearch_s3_user_creds`** (lines 750–762) creates a Secret named `elasticsearch-s3-user-creds` in the ELK namespace containing the S3 access/secret keys from `module.aws_iam_elastic_stack`.

2. **`helm_release.elk`** (lines 836–855) installs the umbrella ELK chart with values that include `local.elk_elasticsearch_values`, which contains (lines 74–80):
   ```yaml
   keystore:
     - secretName: elasticsearch-s3-user-creds
       items:
       - key: aws_s3_user_access_key
         path: s3.client.default.access_key
       ...
   ```

**Real-world ordering requirement — verified against the chart.** The umbrella chart bundles the official Elastic `elasticsearch-7.16.2` chart. I confirmed its `statefulset.yaml`: when `keystore` is set, the StatefulSet declares a `secret` volume named `keystore-<secretName>` and a `keystore` init container that mounts that volume and runs `elasticsearch-keystore add-file` for each key, then copies the resulting keystore to the main container path. This means:
- Kubernetes will not start the Elasticsearch pod while the referenced Secret volume is missing (pod stuck pending; init container cannot run).
- The main container mounts the keystore produced by that init container, so Elasticsearch's S3 snapshot credentials physically come from this Secret.

**Terraform dependency analysis.**
- The `helm_release.elk` arguments reference only `local.elk.*`, `module.elk_namespace`, `var.helm_release_history_size`, and the `local.elk_*_values` heredocs. The Secret appears in the heredoc purely as a literal string (`secretName: elasticsearch-s3-user-creds`) — no attribute of `kubernetes_secret.elasticsearch_s3_user_creds` is interpolated, so **no implicit dependency** exists.
- `eks-elk.tf` contains no `depends_on` for the release — **no explicit dependency** exists.
- Both resources share a dependency on `module.elk_namespace` only, which does not order them relative to each other; Terraform may apply `helm_release.elk` before the Secret.

**Operational consequence.** The Helm provider waits for release resources to be ready by default (`wait = true`, with `timeout = "900"` here). If the release is applied before the Secret, the Elasticsearch pod's init container cannot run, the pod never becomes ready, and the release times out and fails — and even if it didn't fail, Elasticsearch would start without S3 credentials in its keystore, breaking the snapshot repository that the chart's post-install setup registers. The Secret must therefore exist before the release is installed, and Terraform currently has no graph edge enforcing this.

All three diagnostic runs describe the same missing dependency, and it is genuine.

Correct