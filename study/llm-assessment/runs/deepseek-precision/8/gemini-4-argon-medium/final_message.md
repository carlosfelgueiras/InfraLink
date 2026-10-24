The reported missing dependency is **Correct**.

### Analysis

In `modules/project/main.tf`:

1. **`google_project_iam_custom_role.roles` (lines 43–50)** creates project-level custom IAM roles defined in `var.custom_roles`:
   ```hcl
   resource "google_project_iam_custom_role" "roles" {
     for_each    = var.custom_roles
     project     = google_project.project.project_id
     role_id     = each.key
     title       = "Custom role ${each.key}"
     description = "Terraform-managed"
     permissions = each.value
   }
   ```

2. **`google_project_iam_member.additive` (lines 93–98)** creates non-authoritative IAM role bindings on the project for roles specified in `var.iam_additive_roles` and `var.iam_additive_members`:
   ```hcl
   resource "google_project_iam_member" "additive" {
     for_each = length(var.iam_additive_roles) > 0 ? local.iam_additive : {}
     project  = google_project.project.project_id
     role     = each.value.role
     member   = each.value.member
   }
   ```

3. Unlike its authoritative counterpart `google_project_iam_binding.authoritative` (lines 82–91), which explicitly declares `depends_on = [google_project_service.project_services, google_project_iam_custom_role.roles]`, `google_project_iam_member.additive` only references `google_project.project.project_id` and input variables (`var.iam_additive_roles` and `var.iam_additive_members`).
4. When a caller defines custom roles via `var.custom_roles` and assigns them using `var.iam_additive_roles` / `var.iam_additive_members`, GCP IAM requires the custom role to exist before an IAM policy binding can reference it. Without an explicit `depends_on = [google_project_iam_custom_role.roles]`, Terraform may attempt to create `google_project_iam_member.additive` concurrently with or prior to `google_project_iam_custom_role.roles`, causing the IAM binding call to fail.

Correct