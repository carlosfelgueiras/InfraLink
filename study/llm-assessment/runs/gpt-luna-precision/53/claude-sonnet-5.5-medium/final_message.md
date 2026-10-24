The report is correct.

- **Operational requirement:** An HTTP listener references a frontend port on the application gateway. The port can't be deleted while a listener still uses it, so the listener has to be deleted first.
- **How destroy ordering works here:** These `null_resource` objects only act in their destroy-time provisioners, which call `delete_resource.sh`. Terraform destroys a resource before the resources it depends on. So `delete_http_listener` is destroyed first only if it depends on `delete_frontend_port`.
- **Current configuration:**
  - `delete_http_listener` (`http_listener.tf`, line 32) depends on `delete_http_settings`, `delete_backend_pool`, `delete_ssl_cert`, `delete_root_cert` and `set_frontend_port`. It has no dependency on `delete_frontend_port`.
  - `delete_frontend_port` (`frontend_ports.tf`) has no `depends_on` at all.
  - The dependency on `set_frontend_port` doesn't help. That resource's destroy does nothing, so it doesn't order the two deletions.
  - Nothing else in the module links the two. Terraform may therefore delete the frontend port before, or in parallel with, the listener, and the port deletion can fail.
- **Consistency with the module:** The module already uses this pattern for the other deletions. For example, the listener depends on `delete_ssl_cert` and `delete_root_cert`, so the listener is removed before them. The frontend port is the one case left out.

Correct