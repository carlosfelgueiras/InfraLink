The permission uses the local string, not a module output, and nothing else orders it after the module. The `depends_on` at s3.tf line 152 sits on the bucket notification, which is a different resource. A Lambda permission can't be created before the function exists, so the ordering is real and Terraform isn't enforcing it.

Correct