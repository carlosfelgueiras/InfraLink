For each reported missing dependency between a node and a target, inspect the Terraform configuration and determine whether the report is correct.

A report is correct if node should depend on target due to a real-world or operational ordering requirement, but this dependency is not currently expressed in the Terraform configuration through either an attribute reference (implicit dependency) or a depends_on declaration (explicit dependency).

In other words, determine whether target must be created, configured, or otherwise made ready before node can be correctly created or operated, and whether Terraform currently lacks the information necessary to enforce that ordering.

Classify each reported dependency as:
Correct — the missing dependency exists as reported.
Incorrect — no such dependency is required, or the required ordering is already expressed in the configuration.

When making the assessment, consider the semantics of the resources and their attributes, provider/API behavior, and any relevant operational requirements. Do not classify a dependency as necessary solely because the two resources are related; there must be a concrete ordering requirement from target to node.

---

## Diagnostic to assess

- Repository: `marcincuber/eks`
- Commit: `e5f8996c7d6a4732743f5eb24ad297ed9f7c6bf5`
- Module entrypoint: `terraform`
- Source (the resource that should depend on the target): `:module.eks_node_group_al2023`
- Target (the resource it should depend on): `:resource.aws_iam_role_policy_attachments_exclusive.eks_node_group`

Description:

[merged-gpt-6-luna-atleast2of3]
[final-gpt-6-luna-effort-high-run1]
`:module.eks_node_group_al2023` should wait for `:resource.aws_iam_role_policy_attachments_exclusive.eks_node_group` so the managed node group's role permissions are in place before node-group lifecycle operations.

----------------------------------------

[final-gpt-6-luna-effort-high-run2]
The managed node group module receives the node role ARN, but has no dependency on the role's managed-policy reconciliation. EKS node group provisioning should wait until the worker-node policies are attached; the AWS provider documentation recommends this ordering for node groups.

----------------------------------------

[final-gpt-6-luna-effort-high-run3]
The managed node group module receives the node role ARN but does not depend on the role's managed policy attachments. The AWS provider documentation recommends ensuring node-role permissions exist before EKS Node Group handling, including for cleanup of EC2 instances and network interfaces.

----------------------------------------

[merged-deepseek-v4.1-flash-1017-atleast2of3]
[final-deepseek-v4.1-flash-1017-effort-high-run1]
module.eks_node_group_al2023 references aws_iam_role.eks_node_group.arn (create_iam_role = false), but that role's worker-node policies are attached by aws_iam_role_policy_attachments_exclusive.eks_node_group, which has no ordering edge to the node group. The managed node group's instances will fail to join the cluster (missing AmazonEKSWorkerNodePolicy etc.) if the node group is created before the attachments. Add `depends_on = [aws_iam_role_policy_attachments_exclusive.eks_node_group]` to the node group module.

----------------------------------------

[final-deepseek-v4.1-flash-1017-effort-high-run2]
module.eks_node_group_al2023 sets node_role_arn = aws_iam_role.eks_node_group.arn but has no ordering dependency on aws_iam_role_policy_attachments_exclusive.eks_node_group. The EKS managed node group validates that the node IAM role already has the required policies (AmazonEKSWorkerNodePolicy, AmazonEKS_CNI_Policy, ECR read-only, etc.); without the attachment in place, node group creation can fail or nodes fail to join the cluster.

----------------------------------------

[final-deepseek-v4.1-flash-1017-effort-high-run3]
module.eks_node_group_al2023 (which creates the aws_eks_node_group) references aws_iam_role.eks_node_group.arn but not aws_iam_role_policy_attachments_exclusive.eks_node_group, which attaches the required AmazonEKSWorkerNodePolicy/AmazonEKS_CNI_Policy/AmazonEC2ContainerRegistryReadOnly policies. Without an edge to the attachment, the node group may be created before the role's policies are attached, and EKS validates the node role permissions on node group create and needs them on delete. The provider docs require depends_on on the role policy attachments for aws_eks_node_group.

----------------------------------------

[merged-glm-5.3-flash-atleast2of3]
[final-glm-5.3-flash-effort-high-run1]
:module.eks_node_group_al2023 references :resource.aws_iam_role.eks_node_group via node_role_arn, but not the managed policy attachments. Node group instances launched before :resource.aws_iam_role_policy_attachments_exclusive.eks_node_group applies lack AmazonEKSWorkerNodePolicy/AmazonEKS_CNI_Policy and will never join the cluster.

----------------------------------------

[final-glm-5.3-flash-effort-high-run2]
:module.eks_node_group_al2023 only depends on :resource.aws_iam_role.eks_node_group via its node_role_arn, but not on :resource.aws_iam_role_policy_attachments_exclusive.eks_node_group, which attaches the required worker policies (AmazonEKSWorkerNodePolicy, AmazonEKS_CNI_Policy, AmazonEC2ContainerRegistryReadOnly, etc.). If the managed node group is provisioned before the policy attachments propagate, worker nodes cannot join the cluster. :module.eks_node_group_al2023 should wait for :resource.aws_iam_role_policy_attachments_exclusive.eks_node_group (e.g. an explicit depends_on, since only the bare role ARN is referenced).

----------------------------------------

[final-glm-5.3-flash-effort-high-run3]
module.eks_node_group_al2023 depends on aws_iam_role.eks_node_group.arn but not on aws_iam_role_policy_attachments_exclusive.eks_node_group. Managed node group creation requires the node instance role to already have AmazonEKSWorkerNodePolicy, AmazonEKS_CNI_Policy and AmazonEC2ContainerRegistryReadOnly attached; the attachment resource may otherwise be applied in parallel with (or after) the node group.

---

## Your environment

- The current working directory is a snapshot of the repository at the commit above. It contains only the file tree, with no git history. The module entrypoint path is relative to this directory.
- Resource addresses are relative to the module entrypoint. `:resource.<type>.<name>` is declared directly in the entrypoint. `module.<call>:resource.<type>.<name>` is declared inside the module that `module "<call>"` instantiates (follow its `source`).
- You can use web search and web fetch for external information, such as provider documentation. Do not look at this repository's history or later versions (commits, pull requests, issues, or other branches after commit `e5f8996c7d6a4732743f5eb24ad297ed9f7c6bf5`).
- End your final message with a single line containing exactly one word, either `Correct` or `Incorrect`.
