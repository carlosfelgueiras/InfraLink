## Analysis

**The configuration** (`modules/vpc-baseline/main.tf`, instantiated as `vpc_baseline_ap-northeast-3` from `vpc_baselines.tf:102` with `providers = { aws = aws.ap-northeast-3 }`):

```hcl
data "aws_subnets" "default" {
  filter {
    name   = "default-for-az"
    values = [true]
  }
}

data "aws_subnet" "default" {
  for_each = toset(data.aws_subnets.default.ids)
  id       = each.value
}

resource "aws_default_vpc" "default" { tags = ... }

resource "aws_default_subnet" "default" {
  for_each                = data.aws_subnet.default
  availability_zone       = each.value.availability_zone
  map_public_ip_on_launch = false
  tags                    = ...
}
```

**Is the dependency expressed?** No. `data.aws_subnets.default` contains only a static `filter` block — no attribute reference to `aws_default_vpc.default` and no `depends_on` (confirmed by searching the whole repo; every other default resource in the module — flow log, route table, NACL, security group — *does* reference the VPC, but the data source chain does not).

**Is there a real ordering requirement?** Yes, verified against the AWS provider source (`vpc_default_vpc.go`): `aws_default_vpc`'s create function first looks for an existing default VPC (`isDefault=true`) and, when none exists, calls `CreateDefaultVpc` — i.e., it **creates** a missing default VPC, and AWS then creates a default subnet in every AZ as part of that. The `aws_subnets` data source simply issues `DescribeSubnets` with the `default-for-az=true` filter, and Terraform reads data sources at **plan time** when they have no dependencies on pending resources.

So in a region where the default VPC is missing (deleted per security best practices — exactly the scenario this baseline module handles by using `aws_default_vpc`):

1. **Plan**: `data.aws_subnets.default` reads before apply → VPC doesn't exist yet → returns an empty list → `data.aws_subnet.default` and `aws_default_subnet.default` produce **zero** instances.
2. **Apply**: `aws_default_vpc.default` creates the VPC; AWS auto-creates default subnets with `map_public_ip_on_launch = true` and no baseline tags — none of which are hardened, because the plan-time inventory read already happened and missed them.
3. Only a *subsequent* apply would discover and harden them.

The target (default VPC) must therefore be created before the node (subnet inventory data source) is read for the module to operate correctly on first apply, and Terraform currently lacks that ordering information. The suggested remedy is valid and standard: a `vpc-id` filter referencing `aws_default_vpc.default.id` (implicit dependency) or `depends_on` defers the data source read to apply time, after VPC creation.

The report is accurate — the dependency is required and is genuinely absent from the configuration.

Correct