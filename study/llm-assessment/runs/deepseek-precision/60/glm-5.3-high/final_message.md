## Assessment

**Module structure** (all in the entrypoint, `modules/networking/application_gateway_application`):

- `null_resource.set_frontend_port` (`frontend_ports.tf`) — create-time `local-exec` that adds a frontend port to the App Gateway. No destroy provisioner.
- `null_resource.delete_frontend_port` (`frontend_ports.tf`) — `when = destroy` provisioner running `az network application-gateway frontend-port delete` (see `scripts/delete_resource.sh`, `FRONTENDPORT` case).
- `null_resource.delete_http_listener` (`http_listener.tf`) — `when = destroy` provisioner running `az network application-gateway http-listener delete`. Its `depends_on` is `[null_resource.delete_http_settings, null_resource.delete_backend_pool, null_resource.delete_ssl_cert, null_resource.delete_root_cert, null_resource.set_frontend_port]`.

**Analysis:**

1. **Real ordering requirement exists.** An HTTP listener references a frontend port (`set_http_listener` passes `PORT` from the same `frontend_ports` settings collection). Azure will not let a frontend port be deleted while a listener still references it, so on destroy the listener must be removed *before* the frontend port.

2. **Destroy ordering mechanism.** Terraform destroys resources in reverse dependency order: adding `depends_on = [null_resource.delete_frontend_port]` to `delete_http_listener` would make the listener's destroy provisioner run first, then the port deletion — exactly the required sequence. The module already uses this pattern consistently: `delete_request_routing_rule` depends on `delete_http_listener`, `delete_url_path_rule` depends on `delete_http_listener` and `delete_url_path_map`, `delete_http_listener` depends on `delete_ssl_cert`, etc.

3. **The ordering is currently not expressed.** `delete_http_listener` lists `set_frontend_port` — the create-only counterpart, which has no destroy provisioner and therefore provides no relevant destroy-time ordering for the port deletion. A grep confirms nothing in the module references `delete_frontend_port` other than its own declaration, so `delete_frontend_port` is completely unordered relative to `delete_http_listener`. During destroy, Terraform may execute `frontend-port delete` while a listener still references the port; the Azure call fails ("resource in use"), and with `on_failure = fail` the destroy errors out and the listener is never removed.

The report is accurate: the operational ordering requirement (listener deleted before its frontend port) is real, and it is not currently expressed via any implicit or explicit dependency. Adding `depends_on = [null_resource.delete_frontend_port]` to `delete_http_listener` is the correct fix, consistent with how the rest of the module orders its delete resources.

Correct