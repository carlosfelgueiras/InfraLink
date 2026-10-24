The reported dependency is not required. `kubernetes_storage_class_v1.efs` only stores a StorageClass whose `storage_provisioner` is the string `efs.csi.aws.com` and whose `fileSystemId` comes from `module.efs.id`. The Kubernetes API accepts that object as soon as the cluster API is up. It does not check that a CSI driver is installed, and the HashiCorp provider does not wait for one.

`module.eks_blueprints_kubernetes_addons` installs the EFS CSI driver (Helm chart 2.2.9, `storageClasses: []`). That driver is what later fulfills PersistentVolumeClaims. It is not consulted when this StorageClass is created, updated, or deleted, and this example creates no PVC that would need it. The driver can be installed before or after the StorageClass. Both orders are valid.

There is no attribute reference or `depends_on` linking the two, and none is needed. The resources are related, but there is no ordering requirement from the addon to this StorageClass.

Incorrect