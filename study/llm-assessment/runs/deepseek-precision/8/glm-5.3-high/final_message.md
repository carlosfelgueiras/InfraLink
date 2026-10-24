I've inspected the module. Let me verify my analysis of the configuration:

**Findings from `modules/project/main.tf`:**

1. **`google_project_iam_custom_role.roles`** (lines 43–50) creates project-level custom roles with `role_id = each.key`, producing role identifiers of the form `projects/{project_id}/roles/{role_id}`.

2. **`google_project_iam_member.additive`** (lines 93–98) builds its `role` argument from `local.iam_additive`, which is derived **solely from `var.iam_additive_roles` and `var.iam_additive_members`** — plain input variables. Its only resource reference is `google_project.project.project_id`. There is **no implicit dependency** on the custom roles and **no `depends_on`**.

3. **`google_project_iam_binding.authoritative`** (lines 82–91), the sibling resource that handles the parallel input `var.iam_roles`, explicitly declares:
   ```hcl
   depends_on = [
     google_project_service.project_services,
     google_project_iam_custom_role.roles
   ]
   ```
   This confirms the module authors' own recognition that role strings passed via these input variables may reference custom roles created in-module, and that ordering must be enforced defensively via `depends_on` since no implicit reference can exist.

**Assessment of the ordering requirement:**

- A `google_project_iam_member` grant embeds the role identifier in the project's IAM policy; the Cloud IAM API rejects bindings referencing a role that doesn't exist yet. So if a user passes a custom role id (created by `google_project_iam_custom_role.roles` in this module) in `var.iam_additive_roles`, the role must be created before the member grant — a concrete ordering requirement, not just a relationship.
- Since the role string arrives via an input variable, Terraform has no way to infer this dependency implicitly; the only way to express it is `depends_on`, exactly as done for the authoritative binding.
- Without it, the additive members and the custom roles are only ordered transitively through `google_project.project` and can be created concurrently, allowing the grant to race ahead of the custom role creation and fail.

The report is accurate: the dependency exists as described and is currently unexpressed in the configuration.

Correct