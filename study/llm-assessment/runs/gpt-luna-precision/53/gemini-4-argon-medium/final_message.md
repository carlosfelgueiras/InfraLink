In `modules/networking/application_gateway_application/http_listener.tf`, `null_resource.delete_http_listener` runs a `when = destroy` `local-exec` provisioner that deletes the Application Gateway HTTP listener via Azure CLI (`az network application-gateway http-listener delete`), while `null_resource.delete_frontend_port` in `frontend_ports.tf` runs a `when = destroy` provisioner that deletes the frontend port (`az network application-gateway frontend-port delete`).

In Azure Application Gateway, an HTTP listener references a frontend port (`PORT = try(var.settings.frontend_ports[each.value.front_end_port_key].name, ...)`), and a frontend port cannot be deleted while it is still referenced by an existing HTTP listener. Because Terraform destroys resources in reverse dependency order, `null_resource.delete_http_listener` must depend on `null_resource.delete_frontend_port` so that the HTTP listener is deleted before the frontend port on destroy.

Currently, `null_resource.delete_http_listener` has `null_resource.set_frontend_port` in its `depends_on` list instead of `null_resource.delete_frontend_port`:

```hcl
resource "null_resource" "delete_http_listener" {
  depends_on = [null_resource.delete_http_settings, null_resource.delete_backend_pool, null_resource.delete_ssl_cert, null_resource.delete_root_cert, null_resource.set_frontend_port]
```

Because there is no dependency from `null_resource.delete_http_listener` to `null_resource.delete_frontend_port`, Terraform does not enforce deleting the HTTP listener before deleting the frontend port.

Correct