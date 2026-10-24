## Assessment

**Source:** `module.synapse_workspaces` — declared in `synapses.tf` (root entrypoint), instantiating `./modules/analytics/synapse`.
**Target:** `module.keyvault_access_policies` — declared in `keyvault.tf`, instantiating `./modules/security/keyvault_access_policies`.

**1. Does the synapse module write Key Vault secrets? Yes.**
`modules/analytics/synapse/workspace.tf` creates four `azurerm_key_vault_secret` resources (`sql_admin_password`, `sql_admin`, `synapse_name`, `synapse_rg_name`), each with `count = ... == null ? 1 : 0` when `sql_administrator_login_password` is not supplied — i.e., exactly the "generating SQL administrator credentials" case. These secrets are written by the *executing* identity (rover user / pipeline service principal).

**2. Is the ordering requirement real? Yes.**
The `azurerm_key_vault_access_policy` resources created by `module.keyvault_access_policies` (including the `logged_in_user` / `logged_in_aad_app` entries, which explicitly grant the executing principal `secret_permissions = ["Set", ...]`, cf. `modules/security/keyvault_access_policies/access_policy/access_policy.tf` and `examples/data_analytics/200-basic-ml/configuration.tfvars` lines 196–209) are the mechanism by which the executing principal gains the `set` permission required to create those secrets. Vault-creation alone does not confer secret-write rights to the executor, so the grants must be in place before the `azurerm_key_vault_secret` calls, or they fail with authorization errors. This is a concrete ordering requirement, not mere relatedness.

**3. Is the dependency currently expressed? No.**
`module.synapse_workspaces` passes only `keyvault_id = ... module.keyvaults[each.value.keyvault_key].id` — an implicit dependency on vault *existence*, not on the access policies. There is no `depends_on` in `synapses.tf`, and no attribute of the module (or of the nested secret resources) references `module.keyvault_access_policies`. No transitive chain forces the ordering either (both modules merely share a dependency on `module.keyvaults`).

**4. Corroborating pattern:** every other root module that writes Key Vault secrets declares exactly this dependency:
- `mssql_servers.tf` line 9 (`depends_on = [module.keyvault_access_policies]`) — submodule writes 3 secrets
- `virtual_machines.tf` line 5 — VM submodule writes ssh/admin-password secrets
- `azuread.tf` lines 7 (`azuread_applications`) and 57 (`azuread_users`) — submodules write app/user secrets

The synapse module is the only secret-writing module lacking it, so secret creation can race the access-policy grants exactly as reported.

The reported missing dependency is genuine and absent from the configuration.

Correct