## Assessment

**Module inspected:** `modules/networking/application_gateway_application` (files: `http_settings.tf`, `probe.tf`, and the full dependency graph via `grep` of all `depends_on` declarations; scripts `set_resource.sh` / `delete_resource.sh`).

### What these resources do

- **`null_resource.delete_http_settings`** (`http_settings.tf:39`): destroy-time (`when = destroy`) local-exec running `az network application-gateway http-settings delete`. Its `depends_on` is `[null_resource.set_probe, null_resource.delete_backend_pool, null_resource.delete_ssl_cert, null_resource.delete_root_cert]`.
- **`null_resource.delete_probe`** (`probe.tf:37`): destroy-time local-exec running `az network application-gateway probe delete`. It has **no `depends_on`**, and nothing else in the module references it.

### Is there a real ordering requirement? Yes.

- HTTP settings reference custom probes: `set_http_settings` passes `PROBE = each.value.probe` → `az network application-gateway http-settings create ... --probe <name>`, and the module already enforces create-time ordering (`set_http_settings depends_on set_probe`) precisely because the referenced probe must exist first. So settings→probe references are an explicitly supported, first-class case in this module.
- Azure Application Gateway enforces referential integrity: a probe still referenced by a backend HTTP setting **cannot be deleted**. Microsoft's own "remove a probe" guidance requires first clearing the reference from the backend HTTP settings, and the service rejects deletions leaving orphaned references (`InvalidResourceReference`-class errors). So at teardown, the HTTP settings must be deleted before the probe; `delete_probe`'s `on_failure = fail` would otherwise abort the whole destroy.

### Is the ordering already expressed? No.

- Terraform's destroy order is the reverse of the dependency graph (dependents destroyed first). To make the HTTP-settings deletion run before the probe deletion, `delete_http_settings` must depend on `delete_probe`.
- `delete_probe` is completely disconnected from the graph: no `depends_on`, no incoming references. `delete_http_settings` instead depends on `set_probe` — the **create-time** probe resource, which has no destroy provisioner and no graph relation to `delete_probe`, so it conveys no destroy-time ordering. There are no implicit attribute references either (its triggers/env use only variables). The scripts' file-based semaphore serializes gateway operations but does not impose order, so `delete_probe` may run first and fail against the still-referenced probe.
- This also matches the module's own consistent teardown pattern (e.g., `delete_http_listener depends_on delete_http_settings`, `delete_request_routing_rule depends_on delete_http_settings` + `delete_http_listener`): referencers are ordered before the resources they reference — except for the probe edge, which is missing.

The reported dependency (`delete_http_settings` → `delete_probe`) exists exactly as described, in the correct direction, and is absent from the configuration.

Correct