## Analysis

Looking at `examples/observability/eks-cluster-with-amp-amg-opensearch/main.tf`:

- `aws_elasticsearch_domain.opensearch` (lines 160–200) is configured with `vpc_options` (subnet_ids + security_group_ids), meaning it is a VPC-joined OpenSearch/Elasticsearch domain.
- `aws_iam_service_linked_role.opensearch` (lines 202–205) creates the `AWSServiceRoleForAmazonElasticsearchService` service-linked role, gated behind `var.create_iam_service_linked_role`.
- The domain resource contains **no reference** to `aws_iam_service_linked_role.opensearch` (no attribute usage) and **no `depends_on`** clause.

This matches a well-documented AWS provider behavior: when creating an Elasticsearch/OpenSearch domain inside a VPC, AWS requires the service-linked role `AWSServiceRoleForAmazonElasticsearchService` to exist first, since the service uses this role to manage VPC ENIs on your behalf. If the role doesn't already exist in the account and is being created in the same apply, Terraform has no implicit way to know the ordering (since there's no attribute reference), so on a fresh account without that role, a `terraform apply` can fail with an error like "Error creating Elasticsearch domain: ... Before you can proceed, you must enable a service-linked role to give Amazon ES permissions...".

The presence of `aws_iam_service_linked_role.opensearch` strongly suggests the module author intended for it to gate the domain creation (precisely for this reason), but failed to wire up the dependency via `depends_on` or an attribute reference. Without that, Terraform may create both resources in parallel, and the domain could fail if the role isn't ready yet.

This is a genuine, real-world ordering requirement that AWS enforces at the API level, which is not expressed in the current configuration (no implicit or explicit dependency exists between these two resources).

All three reports converge on this same correct finding.

Correct