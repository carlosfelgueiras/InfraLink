## Assessment

**Module context.** In `modules/networking/application_gateway_application`, Application Gateway child objects are managed out-of-band via `az` CLI calls in `null_resource` provisioners. The `set_*` resources run `az ... create` on apply; the `delete_*` resources exist solely to carry `when = destroy` provisioners that run `az network application-gateway ... delete` when the null_resource is destroyed. The only operation these `delete_*` null_resources ever perform is therefore their destroy-time deletion call, and the only semantic effect a `depends_on` edge between two of them can have is on **destroy ordering**.

**The operational requirement is real.** Backend HTTP settings can reference a probe (`PROBE = try(each.value.probe, null)` in `http_settings.tf` line 33, passed as `--probe` in `set_resource.sh` line 102/106), and Azure enforces referential integrity: a probe referenced by a backend HTTP setting cannot be deleted from the gateway. So on teardown, HTTP settings must be removed from the gateway **before** any probe they reference — otherwise `az network application-gateway probe delete` fails or the probe is left orphaned. Today no edge orders these two deletion actions (`delete_probe` has no `depends_on` at all, and `delete_http_settings` depends only on `set_probe`, which carries no destroy provisioner), so the ordering is indeed unexpressed.

**But the reported direction is inverted.** Terraform destroys dependents before their dependencies (reverse of creation order), and a destroy provisioner runs at the start of its resource's destruction. So `delete_probe depends_on [null_resource.delete_http_settings]` would make `delete_probe` the dependent, causing its provisioner — the probe deletion — to run **before** the HTTP settings deletion. That is exactly the failure mode the report warns about, turned from intermittent into deterministic, in both the full-destroy case and the case where a probe and its referencing HTTP setting are removed from configuration together.

The module's own convention confirms the correct direction: the delete resource of the *referencing* object depends on the delete resource of the *referenced* object, so the referencing object is removed from the gateway first:
- `delete_url_path_map` → `depends_on [null_resource.delete_http_settings, ...]` (path maps removed before HTTP settings)
- `delete_http_listener` → `depends_on [null_resource.delete_ssl_cert, ...]` (listeners removed before SSL certs)
- `delete_http_settings` → `depends_on [null_resource.delete_root_cert, ...]` (HTTP settings removed before root certs)

Applying that same semantics to the probe relationship, the genuinely missing edge is:

```hcl
resource "null_resource" "delete_http_settings" {
  depends_on = [null_resource.set_probe, null_resource.delete_probe, ...]
}
```

i.e., `delete_http_settings` depending on `delete_probe` — the **reverse** of what the report specifies. The reported edge (`delete_probe` → `delete_http_settings`) should not be added: it would not make the target ready before the node's operation, but the opposite.

**Conclusion.** The underlying ordering requirement exists and is unexpressed, but the reported dependency as specified (node `delete_probe` depending on target `delete_http_settings`) is backwards for Terraform's destroy semantics — expressing it via `depends_on` would enforce probe deletion *before* HTTP settings deletion, the exact opposite of the required operational ordering. The report's directed edge is therefore not a missing dependency that should exist in the configuration.

Incorrect