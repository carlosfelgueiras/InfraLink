The association does not need to wait on policies created in this module. `firewall_policy_attachments` is an opaque map of policy IDs, and those IDs are often external. A module-created policy ID is server-assigned, so the only valid way to attach one is to pass `firewall_policy_id` back in, which already orders the association after that policy.

Incorrect