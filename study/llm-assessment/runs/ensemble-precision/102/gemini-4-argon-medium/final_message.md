In this module, both `null_resource.delete_probe` and `null_resource.delete_http_settings` only define `local-exec` provisioners with `when = destroy` (invoking `scripts/delete_resource.sh` to delete the probe and HTTP settings from the Azure Application Gateway during resource destruction). They perform no action during creation.

While Azure Application Gateway requires HTTP settings referencing a probe to be deleted before the probe itself is deleted, Terraform destroys resources in the **reverse** order of their dependencies:
- If `null_resource.delete_probe` depended on `null_resource.delete_http_settings`, Terraform would destroy `null_resource.delete_probe` **before** `null_resource.delete_http_settings`, executing the probe deletion script before the HTTP settings deletion script.
- To ensure HTTP settings are deleted before probes during destroy, the dependency must be in the opposite direction: `null_resource.delete_http_settings` must depend on `null_resource.delete_probe` (consistent with how `delete_request_routing_rule`, `delete_url_path_map`, and `delete_http_settings` declare `depends_on` on lower-level `delete_*` resources in this module, and where `null_resource.set_probe` in `null_resource.delete_http_settings.depends_on` at `http_settings.tf:40` appears to be a typo for `null_resource.delete_probe`).

Because making `null_resource.delete_probe` depend on `null_resource.delete_http_settings` would enforce the opposite of the required destroy order, the reported dependency is incorrect.

Incorrect