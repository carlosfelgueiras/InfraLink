The missing destroy ordering is real. `null_resource.delete_http_settings` only lists `null_resource.set_probe` in `depends_on`, and nothing else in the module ties it to `null_resource.delete_probe`.

HTTP settings can be created with `--probe`, which stores a sub-resource reference on the Application Gateway. Azure rejects `az network application-gateway probe delete` while that reference still exists. Microsoft’s own removal procedure clears the HTTP-settings association before removing the probe. `delete_probe` runs that delete with `on_failure = fail` and does not clear the reference.

Terraform destroys a dependent before its dependency. `delete_http_settings` must depend on `delete_probe` so the HTTP-settings cleanup runs first. Depending on `set_probe` does not do that: `set_probe` has no destroy provisioner, so destroying it leaves the Azure probe in place. The file semaphore in the scripts only serializes calls. It does not choose which cleanup runs first.

That matches the module’s other optional references (root certs, SSL certs), whose delete resources are already in `depends_on`. The probe cleanup is the one that was left on the create-time resource.

Correct