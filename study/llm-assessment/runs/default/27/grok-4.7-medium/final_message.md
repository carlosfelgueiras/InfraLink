The exclusion resource has no ordering edge to service enablement, and that edge is required.

`google_logging_project_exclusion.logging-exclusion` only sets `project` from `local.project.project_id`. It does not reference `google_project_service.project_services` and has no `depends_on`. The sibling sink does wait on that resource.

Creating an exclusion calls the Cloud Logging API. That API must be enabled first, and projects created through the Resource Manager API (what `google_project` uses) do not enable `logging.googleapis.com` by default. This module turns it on only through `google_project_service.project_services` when it is listed in `services`, including in the module’s own logging example. Without an explicit dependency, the exclusion can be applied while that enablement is still in progress.

Correct