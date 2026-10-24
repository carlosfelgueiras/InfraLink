No depends_on exists and nothing references the attachment. The Lambda function is created in a VPC, and Lambda needs the EC2 network interface permissions at creation. This is a known real ordering issue.

The function references only `aws_iam_role.scale_down.arn`. That reference doesn't order it after the separate policy attachment. Terraform can therefore create the function before the VPC permissions are attached, which can cause creation failures or slow ENI provisioning. On destroy, the attachment may be removed before the function is deleted, which can leave the ENIs stuck.

Correct