## Assessment

**Node:** `modules/project/alerts.tf:127` — `resource "google_monitoring_alert_policy" "alerts"`
**Target:** `modules/project/main.tf:79` — `resource "google_project_service" "project_services"` (`for_each = toset(local.available_services)`, i.e. arbitrary `var.services`)

### Is the ordering requirement real?

- `google_monitoring_alert_policy` creates policies via the Cloud Monitoring API v3 (`https://monitoring.googleapis.com/v3/projects/{project}/alertPolicies`, confirmed in provider docs). This requires `monitoring.googleapis.com` to be enabled on the target project; otherwise the API returns `403 SERVICE_DISABLED` ("Cloud Monitoring API has not been used in project … or it is disabled").
- The module explicitly supports enabling `monitoring.googleapis.com` itself via `var.services` in the same invocation that defines `var.alerts` (fresh project with alerting, or a reused project where the API is disabled). In that single apply, policy creation can run concurrently with or before API activation.
- This failure mode is real and acknowledged by the provider: the `google_project_service` user guide has a "Newly activated service errors" section describing exactly this 403 when a service is activated and used in the same apply, noting service activation is eventually consistent and not guaranteed complete when the resource finishes provisioning.
- The module's own convention confirms this is considered a required edge here: sibling resources that call APIs the module itself may enable in the same apply all declare `depends_on = [google_project_service.project_services]` — `google_logging_project_sink.sink` (logging.tf:87–92, logging API), `google_cloud_quotas_quota_preference.default` (quotas.tf:50–52, cloudquotas API), `google_compute_project_metadata_item.default` (main.tf:95, compute API), `google_project_iam_*` (iam.tf), `google_project_service_identity.default` (service-agents.tf:136), CMEK bindings (cmek.tf:76), and Shared VPC resources (shared-vpc.tf:95,119,143). Test inventories (`tests/modules/project/examples/logging.yaml`, `quotas.yaml`) show services enabled and their dependent resources created in the same apply.

### Is the dependency currently expressed?

No. `google_monitoring_alert_policy.alerts` has no `depends_on` at all, and its only references are `local.alerts` (factory YAML/`var.alerts`), `local.project.project_id` (→ `google_project.project` / `project_reuse` / `data.google_project.project`), and `google_monitoring_notification_channel.channels` (implicit). None of these connect to `google_project_service.project_services`, directly or transitively — `google_monitoring_notification_channel.channels` itself carries no service dependency either.

### Is it expressible as a data reference?

No — the alert policy consumes no value from the service resource, so an explicit `depends_on` is the only mechanism, exactly as the report states.

## Verdict

The report is correct: `google_monitoring_alert_policy.alerts` should depend on `google_project_service.project_services` (concretely `project_services["monitoring.googleapis.com"]`) so that the Cloud Monitoring API is active before alert policies are created when the module enables it in the same apply, and this dependency is currently missing from the configuration.

Correct