aws_default_vpc "creates" a default VPC if none exists, and AWS's CreateDefaultVpc also creates default subnets. The data source is read at plan time and has no dependency on the VPC resource. So on a first apply where the default VPC is missing, the data source finds no subnets, and those subnets are never managed. The ordering requirement is real, and nothing in the configuration expresses it.

The data source has no `vpc-id` filter and no `depends_on`. `aws_default_subnet` depends on the data source, not on the VPC. Nothing in the data source's configuration refers to `aws_default_vpc.default`.

Adding a dependency would be consistent with the intent of the module.

Correct