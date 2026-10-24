The report is correct.

In `modules/project/shared-vpc.tf`, `google_compute_shared_vpc_service_project.shared_vpc_service` (lines 68–73) takes `host_project` from a variable and `service_project` from `local.project.project_id`. Neither of those references `google_project_service.project_services`, and the resource has no `depends_on`.

The `local.project` definition in `main.tf` doesn't depend on the service resources. When the project is created in this module, `project_id` comes from `google_project.project`. So Terraform has nothing that orders the association after the API enablement.

The sibling `google_compute_shared_vpc_host_project.shared_vpc_host` (line 57) does have `depends_on = [google_project_service.project_services]`.

The ordering requirement is real. Attaching a project as a Shared VPC service project is a Compute Engine XPN operation that involves the service project. On a fresh project, `compute.googleapis.com` has to be enabled first, or the call can fail with a "Compute Engine API has not been used" error.

I didn't check the provider documentation or run an apply. The API-behavior part rests on my understanding of how the XPN association call works.

Correct