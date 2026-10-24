## Analysis

**Configuration facts** (`terraform/layer2-k8s/eks-elk.tf`):

1. **`kubernetes_secret.elasticsearch_credentials`** (line 721) creates a Secret named `elastic-credentials` in the ELK namespace, containing `username` and `password` (from `random_string.elasticsearch_password`).

2. **`helm_release.elk`** (line 836) passes values (`local.elk_elasticsearch_values`, `local.elk_kibana_values`, etc.) that reference the Secret **only by literal name string** in `secretKeyRef` entries, e.g.:

   ```yaml
   - name: ELASTIC_PASSWORD
     valueFrom:
       secretKeyRef:
         name: elastic-credentials
         key: password
   ```

   These `secretKeyRef` references appear for the Elasticsearch, Kibana, Filebeat, APM, and Metricbeat components, plus the Kibana init containers that bootstrap users, roles, snapshot policies, and index templates using those credentials.

3. **Dependency graph check:**
   - The values strings are heredocs with no interpolation of `kubernetes_secret.elasticsearch_credentials` (only `local.kibana_password`, `local.kibana_domain_name`, S3 bucket name, etc.), so no implicit edge exists via `values`.
   - The release references `module.elk_namespace[...].name` for its namespace, and the Secret also references the same module — but a shared dependency does not order the two resources relative to each other.
   - `helm_release.elk` has no `depends_on` declaration.

**Operational requirement check:**

- Kubernetes blocks container start when a `secretKeyRef` points to a nonexistent Secret (`CreateContainerConfigError`). The Elasticsearch pod needs `ELASTIC_PASSWORD` at bootstrap (xpack security enabled), and the Kibana init containers require the credentials to provision users/roles against ES — none of the ELK workloads can run correctly until the `elastic-credentials` Secret exists.
- The Helm provider's `wait` behavior (with `timeout = "900"`) means release readiness depends on the pods becoming ready; if the release installs before the Secret is applied (both run concurrently in the same apply, with no ordering edge), the pods are initially blocked and the release readiness is delayed or, in degraded scenarios, fails.
- Helm itself does not validate the Secret's existence, and nothing in the chart creates `elastic-credentials` — it is exclusively Terraform-managed. Terraform therefore currently lacks the information to enforce secret-before-release ordering, even though a concrete ordering requirement exists (Secret must exist before the chart's pods can start and operate).

The report accurately identifies a real ordering requirement that is not expressed in the configuration.

Correct