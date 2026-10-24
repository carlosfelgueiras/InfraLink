The report is correct.

In `modules/ncc-spoke-ra/main.tf`, `peer_0` takes its appliance details from `local.spoke_vms`. That local is built only from `var.router_appliances`. It uses `internal_ip` and `vm_self_link`, which is the same input the spoke uses. So `peer_0` never references `google_network_connectivity_spoke.spoke-ra`, and nothing in the configuration makes it wait for the spoke. `peer_0` also has no `depends_on`.

The ordering requirement is real. I'm relying on memory here and did not re-check the provider docs. The Compute API rejects a router peer whose `router_appliance_instance` is not yet registered with an NCC spoke. I also recall that the Terraform provider's router-appliance peer example adds `depends_on = [google_network_connectivity_spoke.spoke]`. Without the dependency, Terraform may create `peer_0` in parallel with the spoke and hit a race.

The only other path is through the router and interface resources, and neither depends on the spoke. So adding `depends_on = [google_network_connectivity_spoke.spoke-ra]` to `peer_0` is the right fix.

Correct