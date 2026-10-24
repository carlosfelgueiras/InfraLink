## Assessment

### Configuration facts (verified at commit `f7c25705`)

**Source — `aws_eks_node_group.this`** (`modules/eks-managed-node-group/main.tf:308-391`):
- `node_role_arn = var.create_iam_role ? aws_iam_role.this[0].arn : var.iam_role_arn` → implicit dependency on the **role only**.
- No `depends_on` on the node group.
- When `use_custom_launch_template = true` (the default), it references `aws_launch_template.this[0]` via `local.launch_template_id`/`launch_template_version`.

**Target — `aws_iam_role_policy_attachment.additional`** (`modules/eks-managed-node-group/main.tf:444-449`): attaches the user-supplied `iam_role_additional_policies` (default `{}`) to `aws_iam_role.this[0]`.

**Existing ordering expressions:**
- `aws_launch_template.this` has `depends_on = [aws_iam_role_policy_attachment.this]` (main.tf:289-291), commented *"Prevent premature access of policies by pods that require permissions on create/destroy that depend on nodes"* — but it covers only the **default** (`this`) policies, **not** `additional`.
- Root `aws_eks_cluster.this` likewise depends on its own role's `this` attachments (root `main.tf:84-89`).
- The root module call `module "eks_managed_node_group"` (`node_groups.tf:251-352`) adds no `depends_on`.

### Analysis

1. **The reported dependency is genuinely absent.** The node group and the `additional` attachment are siblings that share only the `aws_iam_role.this` dependency; that creates no ordering between them. Even via the launch-template chain, only `aws_iam_role_policy_attachment.this` is ordered — there is no path (implicit or explicit) from `aws_eks_node_group.this` to `aws_iam_role_policy_attachment.additional`, exactly as the report states.

2. **There is a concrete operational ordering requirement.** The node group's instances assume `aws_iam_role.this`, and the permissions in effect at instance launch are those attached to the role at that moment. `iam_role_additional_policies` exists precisely because nodes/pods need those extra permissions (e.g., EBS CSI in node-role mode, SSM, CNI-related policies). Terraform applies the node group and the attachments concurrently; since IAM policy attachment/propagation is asynchronous, instances can bootstrap and join while the additional policies are not yet in effect — nodes then run without required permissions. The module's own design acknowledges this exact class of requirement by making the launch template wait on the `this` attachments ("prevent premature access of policies by pods"), and the same gap exists symmetrically on destroy (the `additional` attachment can be destroyed — immediately detaching the policy — while node group instances are still running).

3. **No countermanding evidence.** The EKS `CreateNodegroup` API does not validate attached policies, so nothing in provider behavior enforces this ordering — which is precisely why Terraform would need the dependency expressed to guarantee it. The report's factual claims (no dependency path; asynchronous policy propagation; nodes launching without the additional permissions) all check out.

The report is accurate: the ordering requirement is real and is not expressed anywhere in the configuration.

Correct