The report is incorrect: the registration does not need `google_project_service.project_services` to finish first.

- `google_monitoring_monitored_project.primary` in `modules/project/main.tf` has no `depends_on`. Its `name` references `local.project.project_id`, so it already waits for the project to exist.
- `google_project_service.project_services` enables APIs in this project. The monitored-project call, however, goes through the Monitoring API against the metrics scope project, which is each `var.metric_scopes` value and is a different project. Enabling `monitoring.googleapis.com` here does not change whether that call works.
- Adding a project to a metrics scope does not require the Monitoring API to be enabled in the project being added. New projects also normally have `monitoring.googleapis.com` enabled by default, so the "not enabled by default" claim in run 1 looks wrong.

I'm basing this on how the API works and did not check the provider documentation.

Incorrect