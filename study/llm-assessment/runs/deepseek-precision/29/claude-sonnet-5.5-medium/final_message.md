Local.project depends only on google_project, not on the services. Attaching a service project requires the Compute API (compute.googleapis.com) enabled in the service project, and the host project resource already declares this dependency. Whether the API is enabled by this module depends on the services list, but if it is, the ordering is not enforced.

Correct