The report is incorrect. I found no concrete ordering requirement from `google_project_service.project_services` to `google_project_iam_member.oslogin_users`.

- **No API prerequisite:** `oslogin_users` grants the predefined role `roles/compute.osLogin` at project level. Project IAM changes go through the Resource Manager and IAM policy APIs. The grant does not need the Compute API or any of the services in `var.services` to be enabled first.
- **Not the same as the authoritative binding:** `google_project_iam_binding.authoritative` has `depends_on` on the services, but it also depends on the custom roles. That binding can reference roles and services the user configures. The `oslogin_users` grant uses a fixed predefined role and has no such link.
- **Same pattern elsewhere:** `additive`, `oslogin_admins`, `oslogin_iam_serviceaccountuser` and `oslogin_compute_viewer` are also plain `google_project_iam_member` resources with no `depends_on`. This one is not treated differently.
- **Destroy ordering:** `oslogin_meta` has a `depends_on` because it calls the Compute API, which fails if the service is disabled first. Removing an IAM member from the project policy does not have that failure mode.

Incorrect