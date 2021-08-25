# What is it

Map Azure Vault secrets to kubernetes secrets.
Every changes on Azure Vault's secrets will be applied to a
kubernetes secret in a specific namesace.

Specify the namespace via env variable `NAMESPACE`.
If container is running in a pod from within a kubernetes cluster,
its own namespace will be used, thus the `NAMESPACE` env var will be overwritten.

If env var `DRY_RUN` is set, the script does not replace the secrets.

## How to use

See [azure.install.yml](azure.install.yml) for an example on how to install.

NOTE: Of course, Azure Kubernetes needs to be able to access the vault.

You can pass azure credentials via these env vars if you want:

```text
AZURE_CLIENT_ID
AZURE_CLIENT_SECRET
AZURE_TENANT_ID
```

The `azure-vault-to-secret` pod will read all the secrets with the annotation `get-secrets-from-vault`.

For example, this is how a `Secret` is mapped to the `https://your-vault.vault.azure.net/`
vault.

```yaml
---
apiVersion: v1
kind: Secret
metadata:
  name: test-vault-secret
  namespace: fp-test
  annotations:
    get-secrets-from-vault: "https://your-vault.vault.azure.net/"
type: Opaque
```

## Possible Annotations

```bash
get-secrets-from-vault # (required) vault url to which download the secrets
get-secrets-from-vault-camel-to-snake-case # (optional)
get-secrets-from-vault-lower-to-upper-case # (optional)
```

### Why?

You can not store variables named like `NODE_ENV` on azure vault.
As a workaround, you can store that with a camel case format: `NodeEnv`.

Set the following annotations to the secret:

```yaml
---
apiVersion: v1
kind: Secret
metadata:
  name: test-vault-secret
  namespace: fp-test
  annotations:
    get-secrets-from-vault: "https://your-vault.vault.azure.net/"
    get-secrets-from-vault-camel-to-snake-case: true # NodeEnv -> Node_Env
    get-secrets-from-vault-lower-to-upper-case: true # Node_Env -> NODE_ENV
type: Opaque
```

## ENV Variables

```bash
NAMESPACE # (optional) if used outside as stand alone script, specifies the namespace of the secrets that need to be changes. if used in a kubernetes cluster, the pod own namespace will be used.
DRY_RUN # (optional) do not apply changes
AZURE_CLIENT_ID # (optional)
AZURE_CLIENT_SECRET # (optional)
AZURE_TENANT_ID # (optional)
UPDATE_FREQUENCY_IN_S # (optional) how many seconds between runs. default to 60s.
```
