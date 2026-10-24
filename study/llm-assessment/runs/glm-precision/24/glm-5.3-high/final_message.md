## Assessment

**Reported dependency:** `google_monitoring_monitored_project.primary` → `google_project_service.project_services`

**Configuration facts** (`modules/project/main.tf:120-125`):

```hcl
resource "google_monitoring_monitored_project" "primary" {
  provider      = google-beta
  for_each      = toset(var.metric_scopes)
  metrics_scope = each.value          # external scoping project
  name          = local.project.project_id
}
```

The edge is indeed absent from the graph (no `depends_on`, and `local.project.project_id` only creates an implicit dependency on `google_project.project`, not on services). So the question is purely whether the ordering requirement is real.

**Why the report is wrong:**

1. **The API call targets the scoping project, not this project.** Per the magic-modules definition of the resource, the create URL is `v1/locations/global/metricsScopes/{{metrics_scope}}/projects`, where `metrics_scope` comes from `var.metric_scopes` — a list of *external* projects ("List of projects that will act as metric scopes for this project"). The REST reference for `locations.global.metricsScopes.projects.create` confirms the request parent is the scoping project's metrics scope; the monitored project is only a name in the request body. Google's service-enablement checks are evaluated against the project in the request path — the scoping project, which `google_project_service.project_services` (which enables services only in *this* project) cannot help with. Even if API enablement were a precondition, the proposed dependency would not enforce the actual ordering.

2. **No enablement precondition for the monitored project.** The provider's acceptance tests (`resource_monitoring_monitored_project_test.go`) create a brand-new `google_project` with no billing account and no services enabled, then immediately register it into a scoping project's metrics scope — with no `google_project_service` anywhere. These tests run against real APIs and pass.

3. **Google documentation lists no such requirement.** The console guide, the API guide, and the REST reference for the create method list only IAM requirements (Monitoring Admin / `monitoring.metricsScopes.link` on the scoping and monitored projects) — never API enablement in the monitored project. The provider even configures a retry predicate for Monitoring *permission* errors, since IAM propagation is the actual failure mode. Semantically, adding a project to a metrics scope is what *provisions* Monitoring in the monitored project, not something gated on it.

4. **Module design is consistent with this.** `depends_on = [google_project_service.project_services]` is used in this module only for resources whose API calls are made against this project itself (logging sinks, shared-VPC, service agents, compute metadata). `google_monitoring_monitored_project` makes no API call against this project, which is why the authors correctly omit the dependency.

The report's premise ("monitoring.googleapis.com must be enabled in this project before the project can be registered in a metrics scope") is factually incorrect, so no ordering between these two resources is required.

Incorrect