In `terraform/layer2-k8s/eks-elk.tf`, `:resource.helm_release.elk` configures the Elasticsearch chart to mount and load the `elasticsearch-s3-user-creds` Kubernetes Secret into the Elasticsearch keystore (lines 74–80):

```yaml
  keystore:
    - secretName: elasticsearch-s3-user-creds
      items:
      - key: aws_s3_user_access_key
        path: s3.client.default.access_key
      - key: aws_s3_user_secret_key
        path: s3.client.default.secret_key
```

The Secret itself is managed by `:resource.kubernetes_secret.elasticsearch_s3_user_creds` (lines 750–762), which populates the credentials from `module.aws_iam_elastic_stack`. However, `local.elk_elasticsearch_values` hardcodes the secret name `"elasticsearch-s3-user-creds"` rather than referencing `kubernetes_secret.elasticsearch_s3_user_creds`, and `helm_release.elk` has no `depends_on` block. Because `helm_release.elk` waits for deployed pods to become ready (and Kibana's `s3-repo` init container immediately registers the S3 snapshot repository against Elasticsearch), `kubernetes_secret.elasticsearch_s3_user_creds` must exist before `helm_release.elk` is installed.

Correct