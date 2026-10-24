## Analysis

**The two resources** (both in `modules/networking/application_gateway_application`):

- `null_resource.delete_http_listener` (`http_listener.tf:31`) — destroy-time provisioner (`when = destroy`) running `az network application-gateway http-listener delete` (see `scripts/delete_resource.sh:88`), i.e., it removes the listener from the Azure gateway at destroy time.
- `null_resource.delete_frontend_port` (`frontend_ports.tf:24`) — destroy-time provisioner running `az network application-gateway frontend-port delete`. It has **no `depends_on` and no attribute references** — its triggers use only `var.*`/`each.value`, so it has no implicit or explicit edges to any resource.

**Real-world ordering requirement:** An HTTP listener references a frontend port (`http_listener.tf:21`, `set_resource.sh:116` passes `--frontend-port`). An Application Gateway is a single ARM resource, so the CLI delete commands re-PUT the whole gateway config. Removing a frontend port that is still referenced by a listener produces an invalid config and the ARM call fails. Therefore the listener must be removed **before** the frontend port. Since both deletions happen in destroy provisioners, and Terraform destroys in **reverse** dependency order, the required graph edge is `delete_http_listener` → depends_on → `delete_frontend_port` — exactly what the report states.

**Is the ordering already expressed?** No:
- `delete_http_listener`'s `depends_on` (line 32) lists `delete_http_settings`, `delete_backend_pool`, `delete_ssl_cert`, `delete_root_cert`, and `set_frontend_port` — **not `delete_frontend_port`**. The `set_frontend_port` edge is useless at destroy time (set resources run no destroy provisioner) and orders nothing relative to the actual port deletion.
- `delete_frontend_port` has no edges at all, so Terraform may run `az ... frontend-port delete` before (or in parallel with) `az ... http-listener delete`, causing the port deletion to fail and (`on_failure = fail`) abort the destroy.

**Module convention corroborates:** every other delete resource chains to the delete resources of entities it references (`delete_url_path_map` → `delete_http_listener`; `delete_url_path_rule` → `delete_url_path_map`, `delete_http_listener`; `delete_request_routing_rule` → all). The listener references http settings, backend pools, certs — all present in its `depends_on` — and the frontend port, whose delete resource is the one missing (apparently replaced by the ineffective `set_frontend_port` entry).

The reported dependency exists and is missing from the configuration.

Correct