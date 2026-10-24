## Assessment

I inspected `modules/project/main.tf` at the specified commit. The relevant resources:

**Target — `google_project_iam_custom_role.roles`** (lines 43–50):
```hcl
resource "google_project_iam_custom_role" "roles" {
  for_each    = var.custom_roles
  project     = google_project.project.project_id
  role_id     = each.key
  ...
}
```
The module also exports the created role IDs (`outputs.tf` output `custom_roles`), confirming these role IDs are intended to be referenced by callers when granting IAM.

**Node — `google_project_iam_member.additive`** (lines 93–98):
```hcl
resource "google_project_iam_member" "additive" {
  for_each = length(var.iam_additive_roles) > 0 ? local.iam_additive : {}
  project  = google_project.project.project_id
  role     = each.value.role
  member   = each.value.member
}
```

**Evidence the report is correct:**

1. **Real ordering requirement exists.** `var.iam_additive_roles` is a list of arbitrary role strings and may contain IDs of custom roles created by this same module (`projects/<id>/roles/<key>` from `var.custom_roles`). Granting a role via `setIamPolicy`/`getIamPolicy` fails if the role does not exist yet, so the custom role must be created before any IAM member granting it.

2. **The dependency is not expressed.** `role` is a plain string sourced from variables, so there is no implicit (attribute-reference) dependency on `google_project_iam_custom_role.roles`, and the resource declares no `depends_on`. Its only dependency is on `google_project.project` — the same dependency the custom role has — so Terraform may apply the additive member concurrently with, or before, the custom role, causing an apply-time "role does not exist" failure.

3. **The module itself establishes the precedent.** The sibling resource `google_project_iam_binding.authoritative` (lines 82–91) grants roles from the same kind of variable input and explicitly declares `depends_on = [..., google_project_iam_custom_role.roles]` for exactly this reason. The additive member lacks the equivalent protection, an inconsistency the module authors evidently considered necessary on the authoritative path (a comment at line 80 even acknowledges additive roles "might fail due to dynamic values").

4. **No harm / correct fix.** When `var.custom_roles` is empty, `google_project_iam_custom_role.roles` has zero instances, so adding `depends_on = [google_project_iam_custom_role.roles]` to the additive member forces no spurious ordering; when custom roles do exist, the ordering is required whenever any additive grant references one. This matches the module's own established pattern.

The reported missing dependency is genuine: the custom-role resources must exist before additive IAM members granting those roles can be applied, and Terraform currently has no way to infer that ordering.

Correct