## Assessment

**Resources in question** (both in `terraform/layer2-k8s/eks-elk.tf`, both gated on `local.elk.enabled`):

- `kubernetes_secret.kibana_enc_key` (lines 772–783) creates the `kibana-encryption-key` Secret (key `encryptionkey`) in the `elk` namespace.
- `helm_release.elk` (lines 836–855) installs the umbrella chart `../../helm-charts/elk` (bundles kibana-7.16.2.tgz), with `local.elk_kibana_values` passed in `values`.

**The ordering requirement is real.** The Kibana values configure the Kibana deployment with:

```yaml
- name: 'KIBANA_ENCRYPTION_KEY'
  valueFrom:
    secretKeyRef:
      name: kibana-encryption-key
      key: encryptionkey
```

and `kibanaConfig` uses `xpack.security.encryptionKey: ${KIBANA_ENCRYPTION_KEY}`. A container env sourced via `secretKeyRef` cannot be created unless the referenced Secret exists — the pod enters `CreateContainerConfigError` until the Secret appears. Since the Helm provider defaults to `wait = true` (no override here; timeout 900s), the `helm_release.elk` create would block/fail if it runs before the Secret is created.

**The dependency is not expressed.** `helm_release.elk` references the Secret only as a literal string inside the `values` heredocs — there is no attribute reference to `kubernetes_secret.kibana_enc_key` (or to `random_string.kibana_enc_key`), and the resource declares no `depends_on`. Its implicit dependencies are the namespace module, `random_string.kibana_password`, and `aws_s3_bucket.elastic_stack` (via interpolated locals) — nothing that orders it after the Secret. Terraform is therefore free to create (or mutate) the release concurrently with or before the Secret.

The reported missing dependency exists as described: the Secret must exist before the Kibana workload of the release can start correctly, and Terraform currently has no way to enforce that ordering.

Correct