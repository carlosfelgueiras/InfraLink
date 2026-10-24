## Assessment

**Node:** `google_project_iam_member.oslogin_admins` (grants the predefined role `roles/compute.osAdminLogin` on the project) — `modules/project/main.tf:114-119`. It references only `google_project.project.project_id`, so its only dependency is the project resource.

**Target:** `google_project_service.project_services` — `modules/project/main.tf:69-75` (enables the APIs in `var.services`, with `disable_on_destroy = true`).

### Is there a concrete ordering requirement?

**Create/update:** Project-level `google_project_iam_member` operates through the Cloud Resource Manager API (`projects.getIamPolicy`/`projects.setIamPolicy` on `cloudresourcemanager.googleapis.com`). Granting a **predefined** role such as `roles/compute.osAdminLogin` does not require `compute.googleapis.com` (or any service in `var.services`) to be enabled first — predefined roles are globally defined and grantable regardless of service enablement; service enablement only affects role *visibility* in the console. (Custom roles are a different matter, which is why the authoritative binding also depends on `google_project_iam_custom_role.roles`.)

**Destroy:** Removing the member again goes through `setIamPolicy` via Cloud Resource Manager, which is independent of the services in `var.services` being disabled (with `disable_on_destroy = true`). Disabling e.g. `compute.googleapis.com` does not prevent project IAM policy edits. This contrasts with `google_compute_project_metadata_item.oslogin_meta`, which genuinely requires the Compute API — hence its explicit comment "depend on services or it will fail on destroy" (line 57-58). No analogous failure mode exists for an IAM member.

**Module pattern:** None of the other `google_project_iam_member` resources (`additive`, `oslogin_iam_serviceaccountuser`, `oslogin_compute_viewer`, `oslogin_users`) depend on services either; only the authoritative binding (which must also wait for custom roles to exist) and the compute metadata item (with its documented destroy-time failure) do.

### Conclusion

The reports argue purely by analogy ("as the authoritative IAM binding does"), but the authoritative binding's `depends_on` serves the custom-role requirement and precautionary purposes specific to authoritative (full-replacement) semantics. For this additive member granting a predefined role, no API requires any `var.services` service to be enabled for the grant to be created or removed, and order of operations does not affect the end state. There is no concrete ordering requirement from `google_project_service.project_services` to `google_project_iam_member.oslogin_admins`.

Incorrect