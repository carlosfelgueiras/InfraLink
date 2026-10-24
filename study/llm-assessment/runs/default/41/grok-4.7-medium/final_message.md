The reported dependency is not required. `google_logging_organization_settings.default` only sets the organization logging storage location and default-sink flag. That API call needs the caller to already hold `logging.settings.update`. It does not consume anything produced by `google_organization_iam_binding.authoritative`.

Those bindings grant whatever roles and members the caller puts in `var.iam`. They do not create or configure logging settings, and they do not necessarily grant `roles/logging.configWriter` or `roles/logging.admin` to the identity running Terraform. There is no attribute reference or `depends_on` from the settings resource to those bindings, and none is required for the settings update to succeed.

The sink's `depends_on` is a defensive bootstrap pattern for a different resource. It is not evidence that settings cannot be created until those bindings exist. Exclusions and audit configs in the same file also need logging permissions and do not wait on the bindings. The provider only documents an ordering requirement for this resource when a CMEK key is set, which this module does not configure.

Incorrect