The binding sets `folder = local.folder.name`. That local resolves to `google_folder.folder[0]` when `folder_create` is true. Terraform tracks references through locals, so the dependency is already implicit. The binding is applied only after the folder exists, and nothing needs to be added.

The reports say the ordering is not expressed. That is wrong here, because the attribute reference runs through the local.

Incorrect