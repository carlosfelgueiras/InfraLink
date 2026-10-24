I now have a complete, source-verified picture. Let me summarize the assessment.

## Assessment

**The reported missing dependency**: `google_tags_tag_binding.binding` (source) should depend on `google_folder.folder` (target).

**The relevant configuration** (`modules/folder/tags.tf` and `modules/folder/main.tf`):

```hcl
# main.tf
locals {
  folder = (
    var.folder_create
    ? try(google_folder.folder.0, null)
    : try(data.google_folder.folder.0, null)
  )
}

# tags.tf
resource "google_tags_tag_binding" "binding" {
  for_each  = coalesce(var.tag_bindings, {})
  parent    = "//cloudresourcemanager.googleapis.com/${local.folder.id}"
  tag_value = each.value
}
```

**Is there a real ordering requirement?** Yes — a tag binding can only be created on an existing folder, so `google_folder.folder` must be created before the binding when `var.folder_create = true`.

**Is it expressed in the configuration?** Yes, as an implicit dependency through a valid reference chain:

1. The binding's `parent` attribute references `local.folder.id` — an attribute reference creating an implicit dependency on the `local.folder` local value.
2. The `local.folder` expression references `google_folder.folder.0` (inside `try()`), creating an implicit dependency of the local on the folder resource.

I verified against Terraform v1.5.7 and HCL v2.17.0 source that this chain fully registers in the dependency graph:

- **HCL `hclsyntax/variables.go`**: `Variables()` walks the entire expression tree; `FunctionCallExpr.walkChildNodes` visits *all* arguments, with **no special-casing for `try`/`can`**. The traversal `google_folder.folder.0` inside `try()` is collected. (The Terraform `try` docs corroborate: undeclared references inside `try` are static errors, proving static analysis visits those arguments.)
- **Terraform `internal/terraform/node_local.go`**: local value nodes implement `GraphNodeReferencer` (using `lang.ReferencesInExpr` on their expression → yields `google_folder.folder[0]`) and `GraphNodeReferenceable` (addressable as `local.folder`).
- **Terraform `internal/terraform/graph_builder_apply.go`**: the apply graph includes `LocalTransformer` and `ReferenceTransformer`, which connect `binding → local.folder → google_folder.folder[0]`, and `pruneUnusedNodesTransformer` only removes locals *not used by any node* — `local.folder` is referenced by the binding, so it's retained. When the folder is being created, its attributes are unknown at plan time, so the local is evaluated during apply, strictly after the folder is applied.

Therefore Terraform enforces: folder created → `local.folder` evaluated → tag binding created. There is no scenario where the binding is applied before the folder. This is also CFF's standard pattern throughout its modules (IAM bindings, contacts, sinks, firewall policy associations in this very module all rely on the same `local.folder` chain), and the module's two `depends_on` uses are for unrelated cross-service operational ordering, not to compensate for this pattern.

The reports correctly note that a tag binding requires an existing folder, but incorrectly conclude the dependency is unexpressed — they apparently assumed references inside `try()` or through locals don't create implicit dependencies, which is false Terraform semantics. The ordering requirement is already expressed via the attribute-reference chain, so no `depends_on` is needed.

Incorrect