## Assessment

**Configuration facts** (in `modules/project/main.tf`):

- `google_project_iam_member.oslogin_users` (lines 121-126) grants `roles/compute.osLogin` with `project = google_project.project.project_id`, so its only implicit dependency is on the project resource. It has no reference to, nor `depends_on` on, `google_project_service.project_services` (lines 69-75) — so the "not expressed in config" part of the report is accurate.
- Sibling resources behave the same way: `oslogin_iam_serviceaccountuser`, `oslogin_compute_viewer`, `oslogin_admins`, and the `additive` IAM member (lines 93-119) also have no dependency on `project_services`. Only the authoritative `google_project_iam_binding` (lines 87-90, along with custom roles) and `oslogin_meta` (lines 52-59) do.

**Why the ordering requirement does not hold for this resource:**

- `google_project_iam_member` is implemented by the provider as a Cloud Resource Manager `getIamPolicy` → modify → `setIamPolicy` operation. `cloudresourcemanager` is enabled on every project by default (it's the same API that created the project), so the IAM write does not require any of the APIs in `var.services` (e.g. `compute.googleapis.com`) to be enabled first.
- Granting a *predefined* role such as `roles/compute.osLogin` does not require the owning service's API to be enabled; predefined roles exist in the global IAM role registry regardless of per-project API enablement, and the provider performs no service-enabled validation for this resource.
- On destroy, removing the member from the project's IAM policy again only touches Cloud Resource Manager, so it cannot fail because `disable_on_destroy = true` / `disable_dependent_services = true` disabled the services first. This is exactly why `oslogin_meta` — a *Compute* resource (`google_compute_project_metadata_item`), which genuinely needs the Compute API on both create and destroy — carries the `depends_on` with the comment "depend on services or it will fail on destroy". That requirement is specific to service-backed resources and does not transfer to project-level IAM policy entries.
- The authoritative binding's `depends_on` on services (and custom roles) is a defensive sequencing choice for arbitrary user-supplied roles; its existence establishes symmetry, not a concrete ordering requirement for the additive OS Login member. OS Login *functionality* needs the Compute/OS Login APIs at runtime, but that concerns instance metadata and API usage, not the creation or removal of the IAM policy entry itself.

The report's justification ("IAM operations racing service enablement or teardown") is a speculative symmetry argument: there is no create- or destroy-time failure mode for a project IAM member caused by services being enabled or disabled concurrently. Per the evaluation standard — a concrete ordering requirement from target to node — no such requirement exists here.

Incorrect