## Assessment

**Source:** `modules/project/shared-vpc.tf:66-75` — `google_project_iam_member.shared_vpc_host_robots`
**Target:** `modules/project/service-accounts.tf:88-94` — `google_project_service_identity.jit_si`

### What the configuration does

1. **`google_project_service_identity.jit_si`** explicitly generates the service identities for the "just-in-time" services (`secretmanager.googleapis.com`, `pubsub.googleapis.com`, `cloudasset.googleapis.com` — see `local.service_accounts_jit_services`). The module's own comment states: *"Secret Manager SA created just in time, we need to trigger the creation"* — i.e., these robot accounts (`service-{number}@gcp-sa-secretmanager.iam.gserviceaccount.com`, etc.) do **not** come into existence merely from API activation; identity generation is an asynchronous operation triggered by this resource.

2. **`google_project_iam_member.shared_vpc_host_robots`** grants roles in the Shared VPC host project to robot service accounts. Its `member` is built purely from string formatting: `local.service_accounts_robots[each.value.service]` → `format("<template>", local.project.number)`. There is **no attribute reference** to `jit_si` (the member string is computed locally, not derived from the resource), and **no `depends_on`** declaration. Nor is there a transitive chain: `jit_si` depends on `google_project_service.project_services`, but `shared_vpc_host_robots` references neither that resource nor anything downstream of it.

3. **Corroborating evidence within the module:** the parallel resource `google_kms_crypto_key_iam_member.service_identity_cmek` grants IAM to *the exact same* robot accounts (`local.service_accounts_robots[...]`) and explicitly declares `depends_on = [..., google_project_service_identity.jit_si, ...]` (service-accounts.tf:105-112). This shows the module authors recognized that granting IAM to these robots requires the identity to exist first — the GCP `setIamPolicy` API rejects members that don't exist (400 "Service account ... does not exist"), so the grant fails if applied before identity generation completes.

### Conclusion

When `var.shared_vpc_service_config.service_identity_iam` targets one of the JIT services (secretmanager, pubsub, cloudasset) that is also enabled in `var.services`, `shared_vpc_host_robots` can attempt the IAM grant in the host project before `jit_si` has generated the service identity, causing an apply-time failure with an unknown/missing member. Terraform currently has no information to enforce the required ordering: no implicit dependency exists (the member is a locally formatted string), and no explicit `depends_on` is declared. The operational requirement is real, and the module's own handling of the identical member in `service_identity_cmek` confirms it.

Correct