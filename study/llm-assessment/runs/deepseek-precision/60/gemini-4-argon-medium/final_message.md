The reported missing dependency is valid.

In `modules/networking/application_gateway_application/http_listener.tf`, `null_resource.set_http_listener` creates an Application Gateway HTTP listener that references a frontend port (`--frontend-port ${PORT}` created by `null_resource.set_frontend_port`). During teardown, Azure requires any HTTP listener referencing a frontend port to be deleted before the frontend port itself can be deleted.

Because deletion is handled via `when = destroy` `local-exec` provisioners on `null_resource.delete_http_listener` and `null_resource.delete_frontend_port`, Terraform destroys dependent resources before their dependencies. In `null_resource.delete_http_listener` (line 32):

```hcl
depends_on = [null_resource.delete_http_settings, null_resource.delete_backend_pool, null_resource.delete_ssl_cert, null_resource.delete_root_cert, null_resource.set_frontend_port]
```

`null_resource.set_frontend_port` was mistakenly listed instead of `null_resource.delete_frontend_port`. Since `set_frontend_port` has no destroy provisioner and `delete_frontend_port` has no incoming dependency from `delete_http_listener`, Terraform does not enforce destroying `delete_http_listener` before `delete_frontend_port`.

Correct