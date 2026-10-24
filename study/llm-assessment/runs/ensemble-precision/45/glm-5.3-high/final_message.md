## Assessment

**Source** (`modules/project/main.tf:145-150`):
```hcl
resource "google_monitoring_monitored_project" "primary" {
  provider      = google-beta
  for_each      = toset(var.metric_scopes)
  metrics_scope = each.value          # external scoping project
  name          = local.project.project_id  # THIS project (the monitored one)
}
```

**Target** (`modules/project/main.tf:104-111`): `google_project_service.project_services` enables `var.services` **in this module's own project** (`local.project.project_id`) — i.e., in the *monitored* project.

### Findings

1. **The resource's API call is not made in this project's context.** `google_monitoring_monitored_project` calls `POST https://monitoring.googleapis.com/v1/locations/global/metricsScopes/{SCOPING_PROJECT}/projects` — the API consumer is the **scoping project** (`metrics_scope` = `var.metric_scopes`, described as "projects that will act as metric scopes for this project"; gcloud equivalent: `gcloud beta monitoring metrics-scopes create MONITORED --project=SCOPING_PROJECT`). Any Monitoring-API enablement requirement applies to the *scoping* project, an external project that `google_project_service.project_services` (which manages the monitored project's services) can neither enable nor order.

2. **Google's documented prerequisites are IAM-based, not enablement-based.** The "Configure a metrics scope" docs require `roles/monitoring.admin` on the scoping project *and* each monitored project — no API-enablement prerequisite on the monitored project. The provider's own example/test attaches a brand-new project created via `google_project` (no services enabled) to a metrics scope, confirming the monitored project needs no APIs enabled.

3. **The real "fresh project" race is already handled.** The provider defines `IsMonitoringPermissionError` for this resource: "Retry if Monitoring operation returns a 403 ... Waiting for project to be ready for metrics scope" — i.e., IAM propagation on newly created projects, retried automatically. It is not a service-activation race in the monitored project.

4. **Cross-project ordering is already expressed where it matters.** In the repo's own usage (FAST), `metric_scopes = [module.landing-project.project_id]`, and the module's `project_id` output has `depends_on = [..., google_project_service.project_services, ...]` (outputs.tf:121-135). So when the scoping project comes from another module instance, that project's full readiness — including its service enablement — is ordered before `google_monitoring_monitored_project.primary` via the implicit output dependency. The monitored project's own existence is likewise guaranteed via the `local.project.project_id` reference to `google_project.project`.

5. **The report's supporting claim is also inaccurate.** It is not true that "every other API-dependent resource in this module" depends on `project_services`: `google_monitoring_alert_policy.alerts`, `google_monitoring_notification_channel.channels`, `google_essential_contacts_contact.contact`, and `google_compute_project_default_network_tier.default_network_tier` have no such `depends_on`. The blanket pattern is reserved for resources with a concrete enablement need in this project (compute metadata, logging sinks, service agents, shared VPC).

### Conclusion

There is no concrete ordering requirement from `google_project_service.project_services` (services enabled in the *monitored* project) to `google_monitoring_monitored_project.primary`. The Monitoring API call is issued against the external scoping project, prerequisites are IAM roles (retried by the provider), and the relevant cross-project ordering is already expressed through the module-output dependency chain when scoping projects are referenced from other modules.

Incorrect