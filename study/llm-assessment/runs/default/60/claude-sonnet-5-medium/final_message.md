## Analysis

Looking at `frontend_ports.tf` and `http_listener.tf`:

- `null_resource.set_frontend_port` — create-only resource (local-exec on create, no destroy-time provisioner).
- `null_resource.delete_frontend_port` — destroy-only resource (local-exec `when = destroy`) that actually calls `delete_resource.sh` to remove the frontend port from the Application Gateway via the Azure API.
- `null_resource.delete_http_listener` — destroy-only resource whose `depends_on` list is:
  ```
  depends_on = [null_resource.delete_http_settings, null_resource.delete_backend_pool, null_resource.delete_ssl_cert, null_resource.delete_root_cert, null_resource.set_frontend_port]
  ```

Real-world/API requirement: an HTTP listener references a frontend port, so the Azure Application Gateway API will reject deleting a frontend port while a listener still references it. Therefore, on destroy, `delete_http_listener`'s destroy provisioner (which removes the HTTP listener) must run **before** `delete_frontend_port`'s destroy provisioner (which removes the port).

In Terraform, `depends_on` reverses direction for destroy ordering: if `delete_http_listener` depends_on `delete_frontend_port`, the destroy order would be `delete_http_listener` first, then `delete_frontend_port` — which is exactly the correct ordering needed.

Currently, `delete_http_listener` depends on `set_frontend_port` instead. Since `set_frontend_port` has no destroy-time behavior, this edge is irrelevant to the actual deletion sequence relative to `delete_frontend_port`. There is no other depends_on chain or attribute reference anywhere in the module that links `delete_http_listener` to `delete_frontend_port` (confirmed via grep across the module — no implicit reference exists either, since both resources rely only on `each.value`/`var.application_gateway` and local triggers, not on each other's outputs).

This means Terraform has no information forcing `delete_http_listener` to run before `delete_frontend_port` during destroy, so they could be destroyed in parallel or in the wrong order, risking an API error (frontend port deletion failing while still referenced by the listener) or a dangling listener reference.

This confirms the diagnostic's claim precisely: the dependency should point to `delete_frontend_port`, not `set_frontend_port`, and currently does not.

Correct