A StorageClass is only an API object. Kubernetes doesn't check that the provisioner exists when the object is created, so creation succeeds without the CSI driver. The driver is needed only when a PVC is provisioned, and no PVC appears in this configuration. There is no creation-time ordering requirement.

Another point is that the cluster itself is reachable through the kubernetes provider, so the cluster dependency is already expressed. The StorageClass can safely be created before or after the addon.

Incorrect