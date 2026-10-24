The additive IAM member can grant a custom role created in this same module, and nothing in the configuration orders those two resources.

`google_project_iam_member.additive` sets `role` from `var.iam_additive_roles` only. That list is independent of `google_project_iam_custom_role.roles`, so there is no attribute reference and no `depends_on`. Both resources wait only on the project, which lets Terraform create them in parallel.

A project custom role must already exist before it can be bound. The provider requires the form `projects/{project}/roles/{role_id}`, and SetIamPolicy fails if that role is missing. Callers can pass that string: the project id is `${prefix}-${name}` and the role id is the `custom_roles` key. The authoritative binding already handles this with `depends_on = [google_project_iam_custom_role.roles]`. The additive member does not, so the same grant can race on create and on destroy.

Correct