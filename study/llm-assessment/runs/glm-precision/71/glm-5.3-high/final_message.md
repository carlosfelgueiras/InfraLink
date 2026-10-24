## Assessment

**Reported missing dependency:** `module.runner:data.template_file.runners` → `module.runner:module.cache`

### Configuration facts (runner module = repo root)

- `main.tf:140-186` — `data.template_file.runners` renders `template/runner-config.tpl` with `bucket_name = "${local.bucket_name}"` (line 183); the template bakes `BucketName = "${bucket_name}"` into the `[runners.cache.s3]` section that ends up in the runner agent's user-data.
- `main.tf:240-243` — `local.bucket_name = "${var.cache_bucket["create"] ? module.cache.bucket : var.cache_bucket["bucket"]}"`. `cache_bucket.create` defaults to `true` (`variables.tf:388-397`) and the `runner-default` example doesn't override it, so the local resolves to `module.cache.bucket`.
- `main.tf:245` — `module "cache"` creates `aws_s3_bucket.build_cache`; `cache/outputs.tf` exports `bucket` from it. The rendered runners config then flows through `data.template_file.gitlab_runner` → `data.template_file.user_data` → `aws_launch_configuration.gitlab_runner_instance.user_data`.

### Analysis

Both reports assume that because `data.template_file.runners` references `local.bucket_name` rather than `module.cache` directly, the dependency edge is absent. That's a misreading of Terraform semantics: **local values are graph nodes with their own references, not text-substitution macros that hide dependencies.**

I verified this against the Terraform version this repo pins (`ci/bin/terraform.sh` → `TERRAFORM_VERSION=0.11.13`): `terraform/transform_local.go` has a `LocalTransformer` that adds a `NodeLocal` per local value, and `terraform/node_local.go` implements `GraphNodeReferencer` (`References()` = `module.cache.bucket` from the local's expression) and `GraphNodeReferenceable` (`local.bucket_name`). So the graph contains the full chain:

`data.template_file.runners` → `local.bucket_name` → `module.cache` → `aws_s3_bucket.build_cache`

Terraform therefore already enforces exactly the ordering the reports describe: `module.cache.bucket` is unknown until the bucket resource is created, `local.bucket_name` waits on it, the data source waits on the local, and the launch configuration's user-data waits transitively — the runner instance is never provisioned before the cache bucket exists. Run 2's proposed remedy (inlining the local's expression as a direct `module.cache` reference) produces the identical transitive edge and adds nothing. The same propagation holds in 0.12+ semantics.

The underlying ordering requirement is real, but it **is** expressed in the configuration via attribute references (implicit dependency) through the local-value chain — Terraform has all the information needed to enforce it. No `depends_on` is missing.

Incorrect