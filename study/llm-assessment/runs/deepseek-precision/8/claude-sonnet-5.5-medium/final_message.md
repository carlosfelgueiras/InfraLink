The report is correct. `google_project_iam_member.additive` has no dependency on `google_project_iam_custom_role.roles`, either implicit or explicit.

- **No implicit dependency:** The `additive` resource takes its `role` and `member` values from `local.iam_additive`. That local is built only from `var.iam_additive_roles` and `var.iam_additive_members`. Nothing in it references the custom role resource.
- **No explicit dependency:** The `additive` resource has no `depends_on` block.
- **Real ordering need:** The module creates custom roles from `var.custom_roles`, and the same module's callers can pass those roles' IDs in `iam_additive_roles`. A role has to exist before it can be granted, so the grant can fail if it is attempted first.
- **Sibling resource handles it:** `google_project_iam_binding.authoritative` already lists `google_project_iam_custom_role.roles` in its `depends_on` for this reason. The module's own comment also notes that additive roles "might fail due to dynamic values".

Correct