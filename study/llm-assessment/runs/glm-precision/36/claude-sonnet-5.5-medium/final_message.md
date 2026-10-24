The report is incorrect. The tag binding already depends on the folder through an attribute reference.

`google_tags_tag_binding.binding` sets `parent` from `local.folder.id`. The local `folder` is defined as `google_folder.folder.0` when `folder_create` is true. Terraform follows references through locals, so the binding gets an implicit dependency on `google_folder.folder` through that attribute. When `folder_create` is false, the local points to the `google_folder` data source, and the folder already exists, so no ordering is needed.

Incorrect