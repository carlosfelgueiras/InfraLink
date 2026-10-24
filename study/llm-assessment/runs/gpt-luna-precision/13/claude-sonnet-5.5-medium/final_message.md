The report is incorrect.

`google_project_iam_member.oslogin_admins` grants the predefined role `roles/compute.osAdminLogin` on the project. That call goes through the Cloud Resource Manager IAM API, not through any API listed in `var.services`. Predefined roles can be granted whether or not the Compute API is enabled. Disabling a service on destroy also doesn't stop the IAM member from being removed.

The configuration shows no real ordering requirement either:

- `google_project_iam_binding.authoritative` does list `google_project_service.project_services` in its `depends_on`, but its roles come from `var.iam_roles`, which can include roles from the enabled services. That is not true of the fixed OS Login role.
- The sibling resources `oslogin_iam_serviceaccountuser`, `oslogin_compute_viewer` and `oslogin_users` have no such dependency either.
- `google_compute_project_metadata_item.oslogin_meta` does need the dependency, because it calls the Compute API directly and would fail on destroy once Compute is disabled. The IAM members make no such call.

The implicit dependency on `google_project.project.project_id` already ensures the project exists before the grant is made.

Incorrect