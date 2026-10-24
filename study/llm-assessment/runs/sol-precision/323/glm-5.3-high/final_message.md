I have all the evidence needed. Let me summarize the assessment.

## Analysis

**Source:** `google_organization_iam_member.additive` (modules/organization/iam.tf, lines 65–74)

```hcl
resource "google_organization_iam_member" "additive" {
  for_each = (...)
  org_id = local.organization_id_numeric
  role   = each.value.role    # plain string from var.iam_additive / var.iam_additive_members
  member = each.value.member
}
```

**Target:** `google_organization_iam_custom_role.roles` (iam.tf, lines 49–56), created from `var.custom_roles` (role_id = map key, full name `organizations/<org_id>/roles/<role_id>`).

**Findings:**

1. **No dependency is expressed.** The `role` attribute of the member resource comes exclusively from user-supplied strings via `local.iam_additive` (built from `var.iam_additive` and `var.iam_additive_members`). It contains no reference to any attribute of `google_organization_iam_custom_role.roles`, and the resource has no `depends_on`. The only shared value, `local.organization_id_numeric`, is a string split of `var.organization_id` (main.tf line 18) and creates no ordering edge.

2. **A concrete ordering requirement exists.** If an additive grant's role string refers to a custom role created by the same module instance (e.g., `iam_additive = { "organizations/1234567890/roles/myRole" = [...] }` with `"myRole"` also in `var.custom_roles`), the GCP IAM API rejects the grant if the role doesn't exist yet ("Role ... does not exist", HTTP 400). With no dependency edge, Terraform can plan these two resources in parallel on initial apply, causing the grant to fail before the role is created. The README's "Custom Roles" section shows exactly this combined usage (create role + grant it), so the scenario is an intended, supported configuration.

3. **The codebase itself confirms the intended pattern.** The sibling `modules/project/iam.tf` (lines 85–98) implements the identical pattern and explicitly declares:

```hcl
resource "google_project_iam_member" "additive" {
  ...
  depends_on = [
    google_project_service.project_services,
    google_project_iam_custom_role.roles
  ]
}
```

The organization module's `google_organization_iam_member.additive` lacks the corresponding `depends_on` on `google_organization_iam_custom_role.roles` (and no attribute reference substitutes for it), so Terraform currently lacks the information needed to enforce that ordering. The suggested fix — resolving the managed role name when the additive role matches a custom role key (or adding `depends_on`) — matches how the project module handles it.

The report is accurate: the ordering requirement is real whenever an additive grant uses a module-managed custom role, and it is not currently expressed in the configuration.

Correct