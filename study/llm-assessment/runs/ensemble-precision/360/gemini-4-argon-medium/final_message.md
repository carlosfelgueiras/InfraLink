In `examples/organization/master/main.tf`, `resource "aws_organizations_organization" "org"` creates the AWS Organization and enables the service access principals (`access-analyzer.amazonaws.com`, `cloudtrail.amazonaws.com`, and `config.amazonaws.com`), while `module "secure_baseline"` is configured with `account_type = "master"`.

When `account_type = "master"`, `module.secure_baseline`:
1. Queries `data "aws_organizations_organization" "org"` (`bucket.tf`) to construct the S3 bucket policy for the audit log bucket.
2. Provisions IAM Access Analyzers with `type = "ORGANIZATION"` (`analyzer_baselines.tf` / `modules/analyzer-baseline/main.tf`).
3. Provisions an organization-wide CloudTrail trail with `is_organization_trail = true` (`main.tf` / `modules/cloudtrail-baseline/main.tf`).
4. Provisions an AWS Config organization aggregator (`aws_config_configuration_aggregator.organization` in `config_baselines.tf`).

All of these require `aws_organizations_organization.org` and its `aws_service_access_principals` to be created and configured first. Because `module.secure_baseline` neither references `aws_organizations_organization.org` nor declares `depends_on = [aws_organizations_organization.org]`, Terraform has no ordering constraint between them.

Correct