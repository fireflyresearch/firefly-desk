# SSO

Single Sign-On (SSO) lets users authenticate with Firefly Desk using their existing corporate identity provider. The platform implements the OpenID Connect (OIDC) protocol with PKCE (Proof Key for Code Exchange) for secure authorization code flows.

## Supported Providers

Firefly Desk includes pre-configured profiles for these OIDC providers:

| Provider | Roles Claim | Notes |
|----------|------------|-------|
| **Microsoft Entra ID** | `roles` | Requires tenant ID. Roles from Azure AD app roles. |
| **Okta** | `groups` | Add the `groups` scope and configure groups claim in Okta. |
| **Auth0** | `https://{domain}/roles` | Roles from custom namespace claim. Add RBAC rules in Auth0. |
| **Google** | (none) | No roles claim; use Google Groups for RBAC. |
| **Keycloak** | `realm_access.roles` | Roles extracted from realm_access.roles in the ID token. |
| **AWS Cognito** | `cognito:groups` | Roles mapped from Cognito user pool groups. |

## Configuring an OIDC Provider

1. Go to **SSO** in the admin settings and click **Add Provider**.
2. Select the provider type from the dropdown.
3. Enter the **Issuer URL** (e.g., `https://login.microsoftonline.com/{tenant}/v2.0` for Microsoft).
4. Enter the **Client ID** and **Client Secret** from your identity provider's app registration. The client secret is encrypted at rest.
5. Optionally set **Tenant ID** (required for Microsoft Entra ID).
6. Configure **Scopes** -- defaults are pre-filled based on the provider (e.g., `openid profile email` for most providers).
7. Set **Allowed email domains** to restrict which email domains can log in.
8. Save and activate the provider.

## Attribute Mapping

SSO attribute mappings let you forward identity claims to downstream API calls. For example, an `employee_id` claim from the identity token can be injected as an `X-Employee-ID` HTTP header when the agent calls external systems.

Each mapping specifies:

- **Claim path** -- Dot-notation path into the ID token claims (e.g., `custom_claims.hr_id`).
- **Target header** -- The HTTP header or query parameter name.
- **Transform** -- Optional: `uppercase`, `lowercase`, `prefix:VALUE`, or `base64`.
- **System filter** -- Optionally apply the mapping only to calls targeting a specific catalog system.

## Role Mapping

Each provider profile defines which claim contains role information. The platform extracts roles from the ID token and maps them to Firefly Desk RBAC roles. Configure the roles claim and permissions claim per provider to match your identity provider's token structure.

## Tips

- Always test SSO configuration with a non-admin account before rolling out to all users.
- Use allowed email domains to prevent unauthorized accounts from logging in.
- PKCE is enabled by default for all providers, providing extra security for the authorization flow.
- If your provider does not include roles in the token, use attribute mappings and manual role assignment.
