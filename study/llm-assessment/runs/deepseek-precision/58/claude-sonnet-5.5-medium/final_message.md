The report is correct.

- `delete_http_settings` has a destroy-time `local-exec` that removes the HTTP settings (`RESOURCE=HTTPSETTINGS`). Those settings can reference a probe through `PROBE` and `ENABLE_PROBE`, as the create-side `set_http_settings` shows.
- `delete_probe` has a destroy-time `local-exec` that removes the probe, and it has no `depends_on` at all.
- `delete_http_settings` lists `set_probe` in its `depends_on`. `set_probe` does nothing on destroy, so it adds no useful ordering between the two delete resources. Neither delete resource references the other.
- Terraform destroys a dependent before the things it depends on. So `delete_http_settings` depending on `delete_probe` would destroy the HTTP settings first and the probe second. That is the order Azure needs. Application Gateway rejects deleting a probe that an HTTP setting still references.
- With no such dependency, the two destroys can run in either order or in parallel. A probe deletion can then fail because an HTTP setting still references it, and with `on_failure = fail` that aborts the destroy.

Correct