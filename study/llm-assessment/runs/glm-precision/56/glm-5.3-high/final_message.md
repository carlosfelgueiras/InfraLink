I have all the information needed. Let me finalize the analysis.

## Analysis

**The configuration:**

1. **`null_resource.delete_http_listener`** (`modules/networking/application_gateway_application/http_listener.tf:31-57`) has a destroy-time `local-exec` provisioner that runs `az network application-gateway http-listener delete` with `on_failure = fail`. Its `depends_on` (line 32) is `[null_resource.delete_http_settings, null_resource.delete_backend_pool, null_resource.delete_ssl_cert, null_resource.delete_root_cert, null_resource.set_frontend_port]` — **not** `null_resource.delete_frontend_port`.

2. **`null_resource.delete_frontend_port`** (`modules/networking/application_gateway_application/frontend_ports.tf:24-48`) has a destroy-time provisioner that runs `az network application-gateway frontend-port delete` with `on_failure = fail`. It has **no `depends_on` at all**, and its triggers reference only variables (`var.settings.frontend_ports`, `var.application_gateway`), not any resource — so it has zero resource dependencies.

**Operational ordering requirement:** An Azure Application Gateway frontend port that is still referenced by an HTTP listener cannot be deleted; the ARM/az update to remove it fails. So on destroy, the listener deletion (`delete_http_listener`) must run **before** the frontend port deletion (`delete_frontend_port`).

**Is the ordering currently expressed?** No:
- `delete_http_listener`'s destroy-time environment uses only `self.triggers` (listener name, rg, gateway name/id) — no reference to any frontend-port resource, so no implicit dependency exists between the two delete resources.
- The existing `depends_on` on `set_frontend_port` doesn't help: `set_frontend_port` has no destroy provisioner, so its destruction is a no-op and provides no ordering relative to `delete_frontend_port`.
- No other resource creates an indirect chain — `delete_frontend_port` has no dependents and no dependencies, so at destroy time Terraform may run its port-deletion provisioner before (or concurrently with) the listener deletion. The script's file-based semaphore only serializes the `az` calls; it cannot fix wrong ordering — if the port-delete command runs first, it fails against the live gateway, and with `on_failure = fail` the destroy errors out.

**Proposed fix direction is right:** In Terraform, if A `depends_on` B, A is destroyed *before* B. Adding `depends_on = [..., null_resource.delete_frontend_port]` to `delete_http_listener` makes the listener-deletion provisioner run before the frontend-port-deletion provisioner at destroy time — exactly the required ordering.

The reported missing dependency exists as described, and it is not expressed anywhere in the configuration.

Correct