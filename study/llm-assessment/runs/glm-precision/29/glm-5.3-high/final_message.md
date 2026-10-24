## Assessment

**Module:** `modules/folder` at commit `853a9c23`

**Reported missing dependency:** `google_folder_iam_member.bindings` → `google_folder.folder`

### The configuration

`modules/folder/iam.tf` (lines 57–70):
```hcl
resource "google_folder_iam_member" "bindings" {
  for_each = var.iam_bindings_additive
  folder   = local.folder.name
  ...
}
```

`modules/folder/main.tf` (lines 17–34):
```hcl
locals {
  folder = (
    var.folder_create
    ? try(google_folder.folder.0, null)
    : try(data.google_folder.folder.0, null)
  )
}

resource "google_folder" "folder" {
  count        = var.folder_create ? 1 : 0
  display_name = var.name
  parent       = var.parent
}
```

### Analysis

While there is a genuine real-world ordering requirement (an IAM member cannot be bound to a folder that doesn't exist yet), the question is whether Terraform already knows about it. It does:

1. **Implicit reference exists:** `google_folder_iam_member.bindings` sets `folder = local.folder.name`, a direct attribute reference to the local `folder`.
2. **Locals participate in the dependency graph.** In Terraform's plan and apply graphs, `LocalTransformer` inserts a graph node for each local value (`nodeExpandLocal`/`NodeLocal`), which is both referenceable and a referencer. `ReferenceTransformer` then connects `google_folder_iam_member.bindings → local.folder → google_folder.folder` (the local's expression statically references `google_folder.folder` via `try(google_folder.folder.0, null)`; references inside `try` and both branches of a conditional are extracted regardless of which branch evaluates). This is standard, documented Terraform behavior: referencing a local in a resource argument creates transitive implicit dependencies on everything the local references.
3. **Runtime enforcement:** when `var.folder_create = true` (the default), `local.folder` evaluates to `google_folder.folder[0]`, and the IAM member instance physically waits for the folder resource to be applied before its own apply. `AttachDependenciesTransformer` even records these transitive resource dependencies for destroy-time ordering. This `local.folder`-indirection idiom is used deliberately throughout this module (also by `google_folder_iam_binding`, `google_essential_contacts_contact`, `google_org_policy_policy`, logging sinks, etc.) and across the fabric modules (e.g., `local.project` in `modules/project`), and the module's own e2e test (`tftest ... e2e` in README with `folder_create` defaulted to true plus `iam_bindings_additive`) applies successfully precisely because the ordering is enforced.

The reports' premise — "no dependency is expressed/recorded, so the member could be applied before the folder exists" — is factually wrong. Run 3 even concedes the dependency is "expressed via the local.folder local," which is itself a valid implicit dependency expression in Terraform. A static analyzer that fails to trace references through `locals` does not reflect Terraform's actual graph. Adding `depends_on = [google_folder.folder]` would be redundant (and would even be problematic when `folder_create = false`, since the folder resource has `count = 0`).

The required ordering is already expressed in the configuration through an implicit attribute-reference chain, so there is no missing dependency.

Incorrect