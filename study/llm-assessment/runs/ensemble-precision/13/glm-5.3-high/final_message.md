## Analysis

**The resources under assessment**

`modules/project/shared-vpc.tf`:

```hcl
resource "google_compute_shared_vpc_service_project" "shared_vpc_service" {
  provider        = google-beta
  count           = local.svpc_service_config.host_project != null ? 1 : 0
  host_project    = var.shared_vpc_service_config.host_project
  service_project = local.project.project_id
}
```

`modules/project/main.tf`:

```hcl
resource "google_project_service" "project_services" {
  for_each = toset(var.services)
  project  = local.project.project_id
  service  = each.value
  ...
}
```

**Is there a concrete ordering requirement?**

Yes. The attachment API (`compute.googleapis.com/compute/v1/projects/{host}/enableXpnResource`) attaches the current project as a Shared VPC service project, and Google's official "Provision Shared VPC" documentation states this prerequisite explicitly:

- Prerequisites: "Ensure that you have enabled the Compute Engine API ... for your host project **and all service projects** that you plan to attach to the host project."
- Under "Attach service projects": "Before you can attach to a host project, you must enable the Compute Engine API **for the service project**."

So the Compute Engine API (and, per the module's own design, the APIs in `var.services`) must be enabled on the service project — the project this module manages — before the attachment can succeed. On a fresh apply (project creation + API activation + association in one run), the `enableXpnResource` call can race ahead of `google_project_service` completion and fail.

**Is the dependency currently expressed?**

No. `shared_vpc_service` references only `var.shared_vpc_service_config.host_project` and `local.project.project_id`, which transitively depends on `google_project.project` (or `data.google_project.project`) but never on `google_project_service.project_services`. There is no `depends_on`.

**Corroborating pattern in the module**

Every other API-consuming resource in this module is explicitly ordered after service activation: `google_compute_project_metadata_item.oslogin_meta` (`depends_on = [google_project_service.project_services]`), `google_project_iam_binding.authoritative` and `google_project_iam_member.additive` (iam.tf), `google_project_service_identity.jit_si`, the GCS/BQ service-account data sources, and `google_kms_crypto_key_iam_member.service_identity_cmek` (service-accounts.tf). `shared_vpc_service` is the sole exception. The ordering also helps on destroy, since detaching the service project should happen before `disable_dependent_services`/`disable_on_destroy` deactivate the APIs.

The only mitigating nuance is that compute activation only races if `compute.googleapis.com` is included in `var.services` — but that is exactly the module's mechanism for enabling the documented prerequisite, and the ordering edge is needed precisely in the module's intended usage.

**Conclusion**

The Compute API must be enabled on the service project before it can be attached as a Shared VPC service project, `google_project_service.project_services` is how this module enables it, and no implicit or explicit dependency currently orders the attachment after service activation. The reported missing dependency is real.

Correct