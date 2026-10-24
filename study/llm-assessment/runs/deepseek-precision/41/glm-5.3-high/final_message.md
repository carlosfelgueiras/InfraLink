## Assessment

**The reported dependency is real and genuinely missing. Verdict: Correct.**

### What I verified in the configuration

1. **No expressed dependency exists.** In `modules/organization/logging.tf` (lines 59–68), `google_logging_organization_settings.default` takes all inputs from `local.organization_id_numeric`, `var.logging_settings.*`, and `local.ctx.locations` — i.e., variables and locals only. Nothing references `google_organization_iam_binding.authoritative` (declared in `modules/organization/iam.tf`, lines 103–111), and the resource has no `depends_on`. So neither an implicit nor explicit dependency orders these two resources.

2. **The ordering requirement is concrete, not hypothetical.** Creating/updating the settings resource calls the Cloud Logging API (`organizations/{id}/settings` → `updateSettings`), which requires `logging.settings.get`/`logging.settings.update` on the organization (confirmed in Cloud Logging docs). Those permissions are included in `roles/logging.configWriter` and `roles/logging.admin` — organization-scope roles that this module can grant through `google_organization_iam_binding.authoritative` via `var.iam`/`iam_by_principals`. The API call is authenticated by the Terraform runner's credentials, so when the runner's Logging permission derives from a binding this very module creates, the binding must exist before the settings call can succeed.

3. **This module's own history and conventions confirm the pattern.** The sibling `google_logging_organization_sink.sink` carries a blanket `depends_on` on the org IAM bindings (logging.tf lines 107–111), added in Dec 2021 by PR #372 fixing issue #371, whose stated rationale was exactly this scenario: *"If the role happens to be `roles/logging.admin` for example and the user running Terraform is in the group, the sink creation fails"* — i.e., the module's IAM bindings may grant the runner the Logging permissions it needs, so they must be applied first for one-go applies. The same blanket `depends_on` exists on `google_essential_contacts_contact` in `main.tf`. Real-world evidence (Fabric issue #3081) shows this exact settings resource failing with `403: Permission 'logging.settings.update' denied` when the runner lacks the permission.

### Why the "consistency" argument holds

The settings resource is in precisely the same position as the sink: an org-level Logging API call requiring org-level Logging permissions from the same role family (`configWriter`/`admin`), grantable by the module's own bindings. On a first apply where both `iam` and `logging_settings` are set, Terraform has no ordering information, so the settings call can race ahead of the binding creation and fail with 403 — the identical failure mode issue #371 describes for sinks. Since the module deliberately encodes this ordering for the sink (and for essential contacts) but not for the settings resource, the report correctly identifies a missing dependency: `google_logging_organization_settings.default` should depend on `google_organization_iam_binding.authoritative`, and that ordering is currently absent from the configuration.

Correct