`google_project_iam_binding.authoritative` only needs the project. It already waits for that through `project = google_project.project.project_id`, and it calls Resource Manager `setIamPolicy`, not the APIs in `var.services`.

Those bindings do not require the listed services to be enabled first. Predefined roles can be granted whether or not the product API is on, and `members` are caller-supplied strings, not service agents created by this module. Agents that enabling an API does create are exposed as outputs that already depend on `google_project_service.project_services`, and callers use them outside this binding.

The OS Login comparison does not apply. `google_compute_project_metadata_item.oslogin_meta` calls the Compute API, so it must be destroyed before that API is disabled. Removing an IAM binding does not. `disable_on_destroy` and `disable_dependent_services` do not turn off Resource Manager, and forcing bindings to be removed before services is the wrong destroy order when those bindings are what still authorize cleanup. Downstream ordering is already available via the `iam_project_id` output.

Incorrect