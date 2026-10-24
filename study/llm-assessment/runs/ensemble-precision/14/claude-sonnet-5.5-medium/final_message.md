The report is correct.

`google_project_iam_member.shared_vpc_host_robots` in `modules/project/shared-vpc.tf` grants roles on the host project to this project's robot service accounts. The members come from `local.service_accounts_robots`, which are strings built from the project number, such as `service-<num>@compute-system.iam.gserviceaccount.com`. The resource has no `depends_on`, and nothing it references comes from `google_project_service.project_services`.

Those robot service accounts only exist once their APIs are enabled. If the grant runs first, IAM can reject the member as a nonexistent service account.

The same module already treats this as an ordering requirement. `google_kms_crypto_key_iam_member.service_identity_cmek` uses the same robot accounts and explicitly depends on `google_project_service.project_services`. The JIT identities and the GCS and BigQuery service-account data sources have the same dependency.

I did not check whether `local.project` carries a dependency on the project resource. Even if it does, that would order the grant after project creation, not after service enablement.

Correct