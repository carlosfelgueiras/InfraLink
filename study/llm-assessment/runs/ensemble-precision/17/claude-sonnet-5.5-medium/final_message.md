The report is correct. `google_project_iam_member.additive` sets `role` from `each.value.role`, which comes from `var.iam_additive_roles` through `local.iam_additive`. That value is a plain string, so it creates no implicit dependency on `google_project_iam_custom_role.roles`. The resource has no `depends_on` either.

A caller can pass the ID of a custom role created by this module as an additive role. IAM cannot grant that role until it exists, so the grant can fail if Terraform applies it first.

`google_project_iam_binding.authoritative` already declares `depends_on = [google_project_service.project_services, google_project_iam_custom_role.roles]`. The additive resource has no equivalent, so the ordering is real and not expressed.

I did not read `local.iam_additive` to confirm how it builds the role string.

Correct