The values hard-code the secret name as a string, so Terraform has no reference to the secret. The helm_release also has no `depends_on`. The chart's keystore init container needs the secret to exist, so pods would hang or fail without it. The report is correct.

Correct