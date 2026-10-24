## Assessment

**Report:** `google_logging_project_exclusion.logging-exclusion` should depend on `google_project_service.project_services`, because the exclusion is created via the Cloud Logging API, whose activation this module manages — and it currently can race that activation.

### Evidence from the configuration

- `modules/project/logging.tf:138-144` — the exclusion has **no `depends_on` and no attribute reference** to `google_project_service`. Its only dependency is `local.project.project_id` (→ `google_project.project` / data source).
- `modules/project/logging.tf:87-92` — the sibling resource in the *same file*, `google_logging_project_sink.sink`, explicitly declares `depends_on = [ ... , google_project_service.project_services]`, so Terraform already orders sink creation after service enablement, but not exclusion creation.
- `modules/project/main.tf:79-86` — `google_project_service.project_services` enables whatever the user passes via `var.services`; the module's own README examples (e.g. `modules/project/README.md:688-723`) combine `services = ["logging.googleapis.com"]` with `logging_exclusions` in a single apply.
- The module's pervasive convention is that any resource requiring an activated API waits on `google_project_service.project_services` (`iam.tf`, `service-agents.tf`, `cmek.tf`, `quotas.tf`, `outputs.tf`).

### Semantics

`google_logging_project_exclusion` performs a Cloud Logging v2 call (`projects.exclusions.create`) against the project in `project = local.project.project_id`. If `logging.googleapis.com` is not yet enabled in that project, the call fails with `403 SERVICE_DISABLED` ("Cloud Logging API has not been used in project ... or it is disabled"). Google documents the Logging API as enabled by default on new projects, but it can be disabled, and the module supports reusing existing projects (`project_reuse`) and enabling the API through `var.services` — so when `logging.googleapis.com` is (re)enabled by this module in the same apply as the exclusion, the enablement must complete first, and today Terraform has no edge expressing that (both resources only share the `google_project.project` dependency). Since the exclusion has no attribute that can reference the service resource, an explicit `depends_on` — exactly the fix the report proposes, and exactly what the sink already has — is the only way to enforce the ordering.

The report's reasoning is accurate: a real ordering requirement exists (Logging API readiness before exclusion creation) and it is not expressed in the configuration.

Correct