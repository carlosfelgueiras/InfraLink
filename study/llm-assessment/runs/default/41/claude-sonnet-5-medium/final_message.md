## Analysis

I compared `google_logging_organization_settings.default` with its claimed "sibling" `google_logging_organization_sink.sink`, and also checked the analogous resource in the `folder` module (`google_logging_folder_settings.default`) for a baseline pattern.

**Key findings:**

1. `google_logging_organization_settings` only takes `organization`, `disable_default_sink`, and `storage_location` as inputs — all sourced from `var.logging_settings`/locals, with no attribute reference to any IAM resource. This is expected, since this resource configures org-wide logging defaults (e.g., default sink status, storage location), not IAM grants.

2. The permission needed to call this API (`logging.settings.update`, part of `roles/logging.admin`) must be held by the Terraform-executing identity **before** `terraform apply` even starts — it cannot be a permission granted by `google_organization_iam_binding.authoritative`/`bindings` within the same apply, because those IAM binding resources themselves also need pre-existing org-level IAM-admin permissions to execute. There's no bootstrapping relationship where the authoritative bindings "unlock" the settings resource.

3. The `google_logging_organization_sink.sink` resource's `depends_on` relationship to the IAM bindings is tied to its own specific mechanics (its `writer_identity` output feeds several downstream IAM-member resources, and sequencing with authoritative bindings avoids clobbering concurrently-modified org IAM policy around sink-related grants) — not a generic rule that every org-scoped resource must wait on IAM bindings.

4. The sibling module (`modules/folder/logging.tf`) has the exact same `google_logging_folder_settings` resource with **no** `depends_on` on the folder's IAM bindings, confirming this is the established, intentional pattern across the codebase rather than an oversight specific to the organization module.

Since `google_organization_iam_binding.authoritative` manages caller-specified IAM roles for arbitrary principals (not for the Terraform executor's own credentials), and the settings resource requires no permission granted by that binding, there is no genuine ordering requirement from `target` to `node`. The analogy to the sink resource does not hold up to the specific mechanics involved.

Incorrect