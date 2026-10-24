The report is correct.

The child module `github_app_runner_group` reads three of the root-managed secrets through its own data sources. These are `data.aws_secretsmanager_secret.secrets` and `data.aws_secretsmanager_secret_version.secrets`, in `github_app_runner_group/secrets.tf`. The lookup is by name, built from `var.secrets_prefix`.

The module call in `github_app_runner_group.tf` passes only plain values:
- `secrets_prefix` comes from `local.cicd_secrets_prefix`, which is a string built from tenant and deployment variables.
- `github_api` comes from `var.ghes_url`.
- The remaining arguments are variables or tags.

None of these arguments references `aws_secretsmanager_secret` or `aws_secretsmanager_secret_version`. The module call also has no `depends_on`.

The ordering is a real requirement. The `secrets.tf` comments say the root seeds the secrets because, without a seed version, `tf apply` fails. The child's secret-version data source needs a secret with a current version, which only the seed creates. The child's data sources are in the same plan as the root resources, so on a first apply Terraform can try to read them before the secrets and their seed versions exist.

The root module already orders its own data sources correctly. Its `data_cicd_secrets` lookups have `depends_on` on the secret and the seed version, so it is only the child module that lacks this.

Correct