# SSO and OIDC

## Overview

Firefly Desk authenticates users through OpenID Connect (OIDC), a standard authentication protocol built on top of OAuth 2.0. Any identity provider that implements the OIDC specification can be used with Firefly Desk, including Keycloak, Google, Microsoft Entra ID, Auth0, Amazon Cognito, and Okta.

OIDC authentication is enforced only when `FLYDEK_DEV_MODE=false`. In development mode, the platform bypasses authentication entirely and uses a synthetic development user with admin privileges, which removes the need to configure an identity provider for local development.

## How Authentication Works

1. The user navigates to the Firefly Desk frontend and clicks "Sign In."
2. The frontend redirects the user to `GET /api/auth/login`, which redirects to the identity provider's authorization endpoint.
3. The user authenticates with the identity provider (username/password, SSO, MFA, etc.).
4. The identity provider redirects the user back to `FLYDEK_OIDC_REDIRECT_URI` with an authorization code.
5. The backend exchanges the authorization code for an ID token and access token.
6. The backend extracts the user's identity, roles, and permissions from the JWT claims.
7. A session is established and the user is redirected to the application.

The roles and permissions extracted from the JWT are used throughout the user's session to enforce RBAC. This is why correct claim mapping is essential: if the roles claim path does not match the actual token structure, the user will have no roles and will be unable to access protected features.

## General Configuration

These environment variables control OIDC authentication:

| Variable | Description |
|----------|-------------|
| `FLYDEK_OIDC_ISSUER_URL` | The OIDC discovery endpoint base URL. Must end with the realm/tenant path. |
| `FLYDEK_OIDC_CLIENT_ID` | The client ID registered with the identity provider. |
| `FLYDEK_OIDC_CLIENT_SECRET` | The client secret for confidential client authentication. |
| `FLYDEK_OIDC_SCOPES` | Comma-separated OIDC scopes. Default: `openid,profile,email,roles`. |
| `FLYDEK_OIDC_REDIRECT_URI` | The callback URL the provider redirects to after authentication. |
| `FLYDEK_OIDC_ROLES_CLAIM` | The dot-path to the roles array in the JWT. Default: `roles`. |
| `FLYDEK_OIDC_PERMISSIONS_CLAIM` | The dot-path to the permissions array in the JWT. Default: `permissions`. |
| `FLYDEK_OIDC_PROVIDER_TYPE` | Provider type for specialized handling. Options: `keycloak`, `google`, `microsoft`, `auth0`, `cognito`, `okta`. |
| `FLYDEK_OIDC_TENANT_ID` | Tenant or realm ID, required by some providers. |

## Provider Setup Guides

### Keycloak

Keycloak is the recommended identity provider for Firefly Desk because it provides the most complete OIDC implementation with native support for roles, permissions, and fine-grained access control.

**Step 1: Create a realm** (if you do not already have one)

In the Keycloak admin console, create a realm for your organization (e.g., "operations").

**Step 2: Create a client**

- Client ID: `firefly-desk`
- Client Protocol: `openid-connect`
- Access Type: `confidential`
- Valid Redirect URIs: `https://desk.example.com/auth/callback` (or `http://localhost:3000/auth/callback` for local testing)
- Ensure "Service accounts enabled" is checked if you need machine-to-machine access

**Step 3: Configure roles**

Create realm roles that map to Firefly Desk's role model: `admin`, `operator`, `viewer`. Assign these roles to users.

**Step 4: Configure token mappers**

Ensure the "realm roles" mapper is active on the client so that roles appear in the token under `realm_access.roles`.

**Configuration:**

```bash
FLYDEK_OIDC_ISSUER_URL=https://keycloak.example.com/realms/operations
FLYDEK_OIDC_CLIENT_ID=firefly-desk
FLYDEK_OIDC_CLIENT_SECRET=your-client-secret-from-keycloak
FLYDEK_OIDC_REDIRECT_URI=https://desk.example.com/auth/callback
FLYDEK_OIDC_ROLES_CLAIM=realm_access.roles
FLYDEK_OIDC_PERMISSIONS_CLAIM=resource_access.firefly-desk.roles
FLYDEK_OIDC_PROVIDER_TYPE=keycloak
```

### Google

Google provides OIDC authentication through its OAuth 2.0 infrastructure. Google does not natively support role claims in tokens, so role assignment requires additional configuration.

**Step 1: Create OAuth 2.0 credentials**

In the Google Cloud Console, navigate to APIs and Services, then Credentials. Create an OAuth 2.0 Client ID of type "Web application."

**Step 2: Configure the client**

- Authorized redirect URIs: `https://desk.example.com/auth/callback`
- Note the Client ID and Client Secret

**Step 3: Handle role assignment**

Since Google does not include roles in tokens, you have two options:
- Use Google Workspace groups and configure Firefly Desk to map group membership to roles
- Manage role assignments within Firefly Desk after the user authenticates

**Configuration:**

```bash
FLYDEK_OIDC_ISSUER_URL=https://accounts.google.com
FLYDEK_OIDC_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
FLYDEK_OIDC_CLIENT_SECRET=your-google-client-secret
FLYDEK_OIDC_REDIRECT_URI=https://desk.example.com/auth/callback
FLYDEK_OIDC_SCOPES=openid,profile,email
FLYDEK_OIDC_PROVIDER_TYPE=google
```

### Microsoft Entra ID (Azure AD)

Microsoft Entra ID provides OIDC authentication for organizations using the Microsoft ecosystem.

**Step 1: Register an application**

In the Azure Portal, navigate to Entra ID, then App Registrations. Create a new registration.

- Name: `Firefly Desk`
- Supported account types: Choose based on your organization's needs (single tenant is most common)
- Redirect URI: `https://desk.example.com/auth/callback` (type: Web)

**Step 2: Configure client credentials**

Under Certificates and Secrets, create a new client secret. Note the value immediately, as it is only shown once.

**Step 3: Define app roles**

Under App Roles, create roles that match Firefly Desk's model:
- `admin` -- Administrative access
- `operator` -- Operational access
- `viewer` -- Read-only access

**Step 4: Assign users to roles**

In Enterprise Applications, find the Firefly Desk app and assign users to the roles you created.

**Configuration:**

```bash
FLYDEK_OIDC_ISSUER_URL=https://login.microsoftonline.com/your-tenant-id/v2.0
FLYDEK_OIDC_CLIENT_ID=your-application-client-id
FLYDEK_OIDC_CLIENT_SECRET=your-client-secret-value
FLYDEK_OIDC_REDIRECT_URI=https://desk.example.com/auth/callback
FLYDEK_OIDC_ROLES_CLAIM=roles
FLYDEK_OIDC_TENANT_ID=your-tenant-id
FLYDEK_OIDC_PROVIDER_TYPE=microsoft
```

### Auth0

Auth0 is a popular identity-as-a-service platform that supports OIDC authentication with extensive customization options.

**Step 1: Create an application**

In the Auth0 Dashboard, create a new Regular Web Application.

**Step 2: Configure the application**

- Allowed Callback URLs: `https://desk.example.com/auth/callback`
- Allowed Logout URLs: `https://desk.example.com`
- Note the Domain, Client ID, and Client Secret

**Step 3: Configure role claims**

Auth0 does not include roles in tokens by default. You need to add a Post-Login Action (or Rule) that adds roles to the token. The claim must use a namespaced key to comply with Auth0's requirements.

Example Post-Login Action:
```javascript
exports.onExecutePostLogin = async (event, api) => {
  const namespace = 'https://desk.example.com';
  if (event.authorization) {
    api.idToken.setCustomClaim(`${namespace}/roles`, event.authorization.roles);
  }
};
```

**Configuration:**

```bash
FLYDEK_OIDC_ISSUER_URL=https://your-domain.auth0.com/
FLYDEK_OIDC_CLIENT_ID=your-auth0-client-id
FLYDEK_OIDC_CLIENT_SECRET=your-auth0-client-secret
FLYDEK_OIDC_REDIRECT_URI=https://desk.example.com/auth/callback
FLYDEK_OIDC_ROLES_CLAIM=https://desk.example.com/roles
FLYDEK_OIDC_PROVIDER_TYPE=auth0
```

### Amazon Cognito

Amazon Cognito provides authentication for applications built on AWS.

**Step 1: Create a user pool**

In the AWS Console, create a Cognito User Pool with the desired attributes and policies.

**Step 2: Create an app client**

Create an app client with a client secret. Configure the callback URL and logout URL.

**Step 3: Configure groups**

Create Cognito groups that map to Firefly Desk roles: `admin`, `operator`, `viewer`. Assign users to these groups.

**Step 4: Configure the hosted UI** (optional)

If using Cognito's hosted UI, configure it with the appropriate callback URLs.

**Configuration:**

```bash
FLYDEK_OIDC_ISSUER_URL=https://cognito-idp.us-east-1.amazonaws.com/us-east-1_xxxxxxxxx
FLYDEK_OIDC_CLIENT_ID=your-cognito-app-client-id
FLYDEK_OIDC_CLIENT_SECRET=your-cognito-app-client-secret
FLYDEK_OIDC_REDIRECT_URI=https://desk.example.com/auth/callback
FLYDEK_OIDC_ROLES_CLAIM=cognito:groups
FLYDEK_OIDC_PROVIDER_TYPE=cognito
```

### Okta

Okta is an enterprise identity platform with comprehensive OIDC support.

**Step 1: Create an application**

In the Okta Admin Console, create a new Web Application integration using OIDC.

**Step 2: Configure the application**

- Sign-in redirect URIs: `https://desk.example.com/auth/callback`
- Sign-out redirect URIs: `https://desk.example.com`
- Grant type: Authorization Code

**Step 3: Configure groups claim**

In the authorization server settings, add a Groups claim to the ID token:
- Name: `groups`
- Filter: Matches regex `.*` (or filter to specific groups)

**Step 4: Create groups**

Create Okta groups that map to Firefly Desk roles and assign users to them.

**Configuration:**

```bash
FLYDEK_OIDC_ISSUER_URL=https://your-domain.okta.com/oauth2/default
FLYDEK_OIDC_CLIENT_ID=your-okta-client-id
FLYDEK_OIDC_CLIENT_SECRET=your-okta-client-secret
FLYDEK_OIDC_REDIRECT_URI=https://desk.example.com/auth/callback
FLYDEK_OIDC_ROLES_CLAIM=groups
FLYDEK_OIDC_PROVIDER_TYPE=okta
```

## Claim Mapping

Claim mapping is the process of telling Firefly Desk where to find roles and permissions in the JWT token issued by your identity provider. Every provider structures its tokens differently, which is why the claim paths are configurable.

### How Claim Paths Work

The `FLYDEK_OIDC_ROLES_CLAIM` value is a dot-separated path into the JWT payload. For example:

- `roles` -- looks for a top-level `roles` array
- `realm_access.roles` -- looks for `roles` inside the `realm_access` object
- `https://example.com/roles` -- looks for a namespaced claim (common with Auth0)
- `cognito:groups` -- looks for the Cognito groups claim

### Debugging Claim Mapping

If role extraction is not working, decode a JWT token from your provider and inspect its structure. You can use [jwt.io](https://jwt.io) or the following command:

```bash
# Decode the payload of a JWT (second part, between the dots)
echo "YOUR_JWT_TOKEN" | cut -d'.' -f2 | base64 -d 2>/dev/null | python -m json.tool
```

Look for the array that contains role names and use its path as the `FLYDEK_OIDC_ROLES_CLAIM` value.

### Role Name Mapping

Firefly Desk expects role names that match the names defined in its role system: `admin`, `operator`, `viewer`, or custom role names. If your identity provider uses different names (e.g., "administrators" instead of "admin"), you have two options:

1. Rename the roles in your identity provider to match Firefly Desk's expectations
2. Create custom roles in Firefly Desk that match your provider's role names

## Troubleshooting

### Login redirects to the provider but never comes back

- Verify the redirect URI is configured identically in both Firefly Desk and the identity provider
- Check that the provider is accessible from the user's browser (not just the server)
- Ensure the client secret is correct

### User authenticates but has no permissions

- Decode the JWT and verify that the roles claim exists at the expected path
- Check that `FLYDEK_OIDC_ROLES_CLAIM` matches the actual token structure
- Verify that the user is assigned to the correct roles/groups in the provider
- Use `GET /api/auth/me` to see what roles the system extracted

### "OIDC issuer unreachable" at startup

- The backend must be able to reach the issuer URL to fetch the OIDC discovery document
- Check firewall rules, DNS resolution, and SSL certificate validity
- If using a self-signed certificate, ensure it is trusted by the application

### Session expires too quickly

- Check the token lifetime configuration in your identity provider
- Ensure refresh tokens are enabled and have a reasonable lifetime
- Consider increasing the access token lifetime if users are being logged out frequently
