Nothing in the module links the analyzer to the organization. The `module "secure_baseline"` call has no `depends_on`, and none of its inputs reference `aws_organizations_organization.org`. In `modules/analyzer-baseline`, the analyzer's type comes from `var.is_organization`, which is `local.is_master_account`. It does not reference the organization.

The organization resource is what enables the `access-analyzer.amazonaws.com` service access principal. An ORGANIZATION-type analyzer needs the organization and that trusted access in place before it can be created. The AWS provider documentation for this resource also shows `depends_on = [aws_organizations_organization.example]` for organization analyzers. I did not re-fetch that page here, so that point is from memory.

The report is correct.

Correct