## Assessment

**Reported dependency:** `google_folder_iam_audit_config.default` → `google_folder.folder` — claimed missing.

### Relevant configuration

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

`modules/folder/logging.tf` (lines 30–32):

```hcl
resource "google_folder_iam_audit_config" "default" {
  for_each = var.logging_data_access
  folder   = local.folder.name
  ...
}
```

### Analysis

- The ordering requirement is real: an IAM audit config can only be set on an existing folder. However, that ordering **is already expressed in the configuration** as an implicit dependency.
- When `var.folder_create = true` (the default, and the only case where `google_folder.folder` exists at all), `local.folder` evaluates to `google_folder.folder[0]`, so `folder = local.folder.name` is an attribute reference to `google_folder.folder.name` — a computed attribute unknown until the folder is created. Terraform therefore must create the folder before applying the audit config, and enforces this edge.
- Terraform's static reference analysis records references through locals, both branches of a conditional, and inside `try()`. So the graph edge `google_folder_iam_audit_config.default → local.folder → google_folder.folder` exists; the tool producing this diagnostic simply failed to resolve the local/conditional/`try` chain.
- When `var.folder_create = false`, the managed `google_folder.folder` has `count = 0` and does not exist — no dependency on it is (or can be) required.

This is the standard pattern used consistently across the module (`google_folder_iam_binding`, `google_logging_folder_sink`, `google_essential_contacts_contact`, org policies, etc. all use `local.folder.name`/`local.folder.id` without `depends_on`), precisely because the implicit dependency via the attribute reference already guarantees ordering. No explicit `depends_on` is needed.

The report is **Incorrect** — the dependency on `google_folder.folder` is already expressed via the attribute reference chain (`folder = local.folder.name` → `local.folder` → `google_folder.folder`), so Terraform does have the information necessary to enforce the ordering.

Incorrect