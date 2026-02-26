---
type: tutorial
---

# Credentials

The Credential Vault securely stores API keys, tokens, passwords, and other secrets used by catalog system integrations. All credential values are encrypted at rest using a pluggable Key Management Service (KMS) architecture.

## How Credentials Work

Each credential is associated with a catalog system and has:

- **Name** -- A descriptive label (e.g., "CRM API Key" or "ERP OAuth Token").
- **Type** -- The kind of credential: API key, bearer token, basic auth, OAuth2 client credentials, etc.
- **Encrypted value** -- The secret itself, encrypted before storage and decrypted only when needed for an API call.
- **Expiration date** -- Optional expiry tracking so you know when to rotate.
- **Last rotated** -- Timestamp of the most recent rotation for audit purposes.

When the agent calls an external system endpoint, the platform automatically retrieves the matching credential, decrypts it, and injects it into the HTTP request headers per the system's authentication configuration.

## KMS Providers

Firefly Desk supports multiple encryption backends. Configure the provider via the `FLYDESK_KMS_PROVIDER` environment variable:

| Provider | Setting | Requirements |
|----------|---------|-------------|
| **Fernet** (default) | `fernet` | Set `FLYDESK_CREDENTIAL_ENCRYPTION_KEY` to a Fernet-compatible key |
| **AWS KMS** | `aws` | Set `FLYDESK_AWS_KMS_KEY_ARN` and optionally `FLYDESK_AWS_KMS_REGION` |
| **Google Cloud KMS** | `gcp` | Set `FLYDESK_GCP_KMS_KEY_NAME` |
| **Azure Key Vault** | `azure` | Set `FLYDESK_AZURE_VAULT_URL` and `FLYDESK_AZURE_KEY_NAME` |
| **HashiCorp Vault** | `vault` | Set `FLYDESK_VAULT_URL`, `FLYDESK_VAULT_TOKEN`, and optionally `FLYDESK_VAULT_TRANSIT_KEY` |
| **NoOp** (dev only) | `noop` | No encryption -- plaintext storage for development/testing |

For production deployments, use a cloud KMS provider (AWS, GCP, Azure) or HashiCorp Vault. The default Fernet provider is suitable for single-server deployments where you manage the encryption key yourself.

## Managing Credentials

From the admin console you can create, update, and delete credentials. The encrypted value is never displayed after creation -- you can only replace it with a new value. Deletion is permanent and will break any system that depends on the credential.

## Tips

- Never use the NoOp provider in production -- it stores secrets in plaintext.
- If no Fernet key is configured, the system falls back to a static development key and logs a warning. This is not secure for production.
- Rotate credentials regularly and use the expiration date field to track rotation schedules.
- The audit log records all credential operations (create, update, delete) for compliance.
