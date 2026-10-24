Attaching a project as a Shared VPC service project calls the Compute Engine XPN API (`compute.googleapis.com`) on the service project. This call is made against the service project, and the API can't be used until it is enabled there.

In `modules/project/shared-vpc.tf`, `google_compute_shared_vpc_service_project.shared_vpc_service` has no `depends_on`. Its only reference to this project is `local.project.project_id`. That value comes from `google_project.project` (or the `google_project` data source), not from `google_project_service.project_services`. So nothing in the configuration makes the association wait for API activation.

The other resources in the module that call project-level APIs do declare this ordering. Examples are `google_compute_project_metadata_item.oslogin_meta`, the IAM resources and the service-account resources, which all use `depends_on = [google_project_service.project_services]`. `shared_vpc_service` is missing it.

On a fresh project where `compute.googleapis.com` is in `var.services`, the association can be attempted before the API is enabled and fail. I did not run Terraform or check the provider documentation for this.

Correct