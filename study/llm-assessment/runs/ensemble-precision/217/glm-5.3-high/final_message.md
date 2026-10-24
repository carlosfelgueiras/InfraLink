I now have the complete picture. Let me finalize my analysis:

## Assessment

**Target**: `aws_secretsmanager_secret.cicd_secrets` — declared directly in the entrypoint `modules/platform/forge_runners/secrets.tf` (lines 46–57). It creates 5 Secrets Manager secrets named `${local.cicd_secrets_prefix}github_actions_runners_app_key`, `..._app_id`, `..._app_client_id`, `..._app_installation_id`, `..._app_name`, where `local.cicd_secrets_prefix = "/cicd/common/${var.tenant.name}/${var.deployment_config.secret_suffix}/"` (pure variables).

**Node**: `data.aws_secretsmanager_secret.secrets` — declared in `modules/platform/forge_runners/github_actions_job_logs/secrets.tf` (lines 15–18). It looks up 3 of those exact secrets **by name**: `${var.secrets_prefix}github_actions_runners_app_key`, `..._app_id`, `..._app_installation_id`. The entrypoint passes `secrets_prefix = local.cicd_secrets_prefix` (`github_actions_job_log.tf` line 10).

**Real ordering requirement — yes.** The child module's data source resolves, by name, exactly the secrets the target resource creates in the same configuration/apply. On a fresh deployment (empty state), the data source's inputs are all known at plan time, so it is read during the plan/refresh phase — before `aws_secretsmanager_secret.cicd_secrets` is created during apply — and the name-based lookup fails ("Secret not found"), blocking the run. The target must exist before the node can be read.

**Is the ordering expressed? No:**
- **No implicit dependency**: `secrets_prefix` is a string interpolated solely from variables (`var.tenant.name`, `var.deployment_config.secret_suffix`); no attribute of `aws_secretsmanager_secret.cicd_secrets` flows into the child module's data source, so no graph edge exists.
- **No explicit dependency**: the data source has no `depends_on` in the child module, and the `module "github_actions_job_logs"` block in `github_actions_job_log.tf` has no `depends_on` either.

**Corroborating evidence within the same file**: the parent module explicitly recognized this exact requirement for its own lookups — `data.aws_secretsmanager_secret.data_cicd_secrets` carries `depends_on = [aws_secretsmanager_secret.cicd_secrets]` (secrets.tf lines 93–95) — but no equivalent link exists for the child module's name-based lookup. (A `depends_on` on the module block would propagate the ordering to the data source, deferring its read until after the secrets are created.)

Both runs of the diagnostic describe this same genuine, unexpressed ordering: the data source must not be read until the secret resource has been created, and Terraform currently lacks the information to enforce it.

Correct