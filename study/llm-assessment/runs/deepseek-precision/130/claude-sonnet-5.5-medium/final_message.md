Lambda creation with a VPC config does require the role to have ENI permissions at creation time. AWS checks `ec2:CreateNetworkInterface` and related permissions when the function is created, and the call fails if the role lacks them. The attachment isn't referenced by the function and there is no `depends_on`, so Terraform doesn't enforce the order.

Correct