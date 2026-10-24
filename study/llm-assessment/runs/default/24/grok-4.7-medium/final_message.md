`google_monitoring_alert_policy.alerts` calls the Cloud Monitoring API and only waits on the project (and, when used, notification channels). It has no attribute reference or `depends_on` for `google_project_service.project_services`.

Projects created through this module do not get Console/gcloud default APIs, so `monitoring.googleapis.com` is only ready if this module enables it. Without an explicit dependency, policy creation can run in parallel with that enablement and fail. The same `depends_on` pattern is already used for other API-backed resources in the module.

Correct