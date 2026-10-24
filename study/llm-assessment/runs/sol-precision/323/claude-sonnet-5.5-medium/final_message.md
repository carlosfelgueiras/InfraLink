The report is correct. In `modules/organization/iam.tf`, `google_organization_iam_member.additive` takes `role` from `each.value.role`. That value comes from the string inputs `var.iam_additive` and `var.iam_additive_members`. The resource has no `depends_on` and no reference to `google_organization_iam_custom_role.roles`.

If an additive grant uses a custom role created by this module, the role must exist before the grant can succeed. Terraform has no way to know that, so it can try the grant first and fail.

The other resources in the module (firewall policies, outputs, organization policies) list both the roles and the additive grants in their `depends_on`. That shows the ordering is only enforced for them, not for the grant itself.

Correct