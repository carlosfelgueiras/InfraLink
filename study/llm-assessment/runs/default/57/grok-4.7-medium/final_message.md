The reported dependency is not required. `delete_http_listener` does not reference `delete_frontend_port`, and nothing else in the module orders those two resources. That gap does not matter, because `delete_frontend_port` never deletes a frontend port.

Its destroy provisioner runs `delete_resource.sh` with `RESOURCE=FRONTENDPORT`, and that branch calls `az network application-gateway address-pool delete`, the same command as the backend-pool case. It does not call `frontend-port delete`. The matching create path in `set_resource.sh` also creates an address pool, not a frontend port. Listeners are created with `--frontend-port` against a port name from `var.settings.frontend_ports` or the parent gateway’s `frontend_ports`, which this null resource does not own.

An HTTP listener does not reference an address pool, so deleting one cannot fail because the other still exists. The real listener-to-port constraint is an Azure rule, but it is not enforced by these two resources. Depending on `set_frontend_port` only orders destruction against a create-only resource whose destroy provisioner does nothing; it does not create a needed edge to `delete_frontend_port`.

Incorrect