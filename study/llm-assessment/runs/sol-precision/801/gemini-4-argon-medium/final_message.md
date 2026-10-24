The reported diagnostic is **Correct**.

### Analysis

1. **Configuration Inspection**:
   - In `data.tf` (lines 22–137), `data "aws_iam_policy_document" "eks_key"` defines the KMS key policy used by `module "kms"` (`main.tf`, line 16) to create `aws_kms_key.this` (`modules/aws-kms/main.tf`).
   - Within `data.aws_iam_policy_document.eks_key`, two statements (`"Allow use of the key"` and `"Allow attachment of persistent resources"`) specify the EKS cluster IAM role as an AWS principal using `local.cluster_iam_role_pathed_arn` (`data.tf`, lines 107 and 127).
   - In `locals.tf` (lines 145–147), when `var.create_iam_role` is `true` (the default), `local.cluster_iam_role_pathed_arn` is constructed via string interpolation from the partition, caller identity account ID, `var.iam_role_path`, and `var.cluster_name` (`arn:${local.context.aws_partition_id}:iam::${local.context.aws_caller_identity_account_id}:role/${local.cluster_iam_role_pathed_name}`), without referencing `module.aws_eks`.
   - Meanwhile, the IAM role itself is created inside `module.aws_eks` (`terraform-aws-modules/eks/aws`), and `module.aws_eks` consumes `module.kms[0].key_arn` via `cluster_encryption_config` (`main.tf`, lines 4 and 75).

2. **Operational & Provider Behavior**:
   - AWS KMS validates principal ARNs in key policies upon key creation/update and rejects policies that reference non-existent IAM principals with a `MalformedPolicyDocumentException` (`Policy contains a statement with one or more invalid principals`).
   - Because `data.aws_iam_policy_document.eks_key` only depends on data sources and input variables, all of its inputs are known before `module.aws_eks` creates the cluster IAM role. Consequently, `module.kms` attempts to create the KMS key before `module.aws_eks` has created the cluster IAM role, causing KMS key creation to fail unless the role already exists.
   - Referencing `module.aws_eks.cluster_iam_role_arn` in `data.aws_iam_policy_document.eks_key` properly orders the evaluation of the policy document (and subsequent KMS key creation) after the IAM role resource inside `module.aws_eks`, while avoiding a circular dependency with the EKS cluster resource itself (which depends on the KMS key ARN).

Correct