The report is correct. Nothing in the configuration makes the worker ASG wait for the CNI policy attachment.

- **No ordering today:** `aws_autoscaling_group.workers` (`workers.tf`) takes its launch configuration from `aws_launch_configuration.workers`. That chain reaches `aws_iam_instance_profile.workers`, then the role. Nothing in it references `aws_iam_role_policy_attachment.workers_AmazonEKS_CNI_Policy`. The attachment hangs off the role as a separate sibling resource, and the ASG has no `depends_on`.
- **Real requirement:** The `aws-node` CNI pods on the workers need `AmazonEKS_CNI_Policy` to assign pod IPs. The `attach_worker_cni_policy` variable description warns that without these permissions nodes cannot join the cluster. Instances can launch before the attachment exists, so the nodes may start with no CNI permissions and sit NotReady until the policy lands.
- **Precedent in the module:** `node_groups.tf` already passes `role_CNI_Policy`, `role_NodePolicy` and `role_Container` to the managed node groups as ordering inputs. So the module treats this ordering as required, and the self-managed ASG path is the one without it.

One caveat: `aws-node` retries, so the node would probably recover once the attachment completes. That makes the effect transient rather than permanent. It is still a real ordering gap that Terraform has no information to enforce.

Correct