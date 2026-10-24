Based on my inspection of the Terraform configuration:

**Current state:**
- `null_resource.set_probe` creates the probe (create-time provisioner only, no destroy-time action)
- `null_resource.delete_probe` has a destroy-time provisioner that runs `az network application-gateway probe delete` — but it has **no `depends_on`** at all, and no other resource references or depends on it
- `null_resource.delete_http_settings` has a destroy-time provisioner that runs `az network application-gateway http-settings delete`, and its `depends_on = [null_resource.set_probe, null_resource.delete_backend_pool, null_resource.delete_ssl_cert, null_resource.delete_root_cert]`

**Why this matters for destroy ordering:**
In Terraform, `depends_on = [B]` on resource `A` means `A` is created after `B`, and consequently `A` is destroyed *before* `B` (reverse order). Since `set_probe` has no destroy-time provisioner, the `depends_on` edge to `set_probe` is inert for teardown purposes — it doesn't establish any ordering relative to `delete_probe`, which is a completely separate resource with no edges to/from `delete_http_settings`.

**Real-world requirement:**
Looking at `scripts/delete_resource.sh`, deleting a probe uses `az network application-gateway probe delete`. The Azure Application Gateway API rejects deletion of a probe that is still referenced by an HTTP settings object (`PROBE` / `enable_probe` field in `http_settings.tf` references the probe). Therefore the HTTP settings must be deleted (or have their probe reference removed) *before* the probe itself is deleted.

**Conclusion:**
Since Terraform's dependency graph has no edge connecting `delete_http_settings` and `delete_probe`, their destroy order is unconstrained — Terraform could destroy `delete_probe` before `delete_http_settings`, which would cause the `az network application-gateway probe delete` command to fail (probe still in use), since `on_failure = fail` is set. The configuration should add `null_resource.delete_probe` to `delete_http_settings`'s `depends_on` list to guarantee HTTP settings are torn down first. The current `depends_on` on `set_probe` does not achieve this.

This confirms the report's diagnosis.

Correct