---
type: faq
---

# Troubleshooting

## Backend Will Not Start

The most common cause of startup failures is a Python version mismatch. Firefly Desk requires Python 3.13 or later. Verify your active Python version with `python --version` or `python3 --version`. If you are using pyenv or similar version managers, ensure that the correct version is active in the project directory.

If the Python version is correct, the next likely cause is missing dependencies. Run `uv sync` to ensure all packages are installed. The `uv sync` command uses the lockfile to install exact dependency versions, so if the lockfile was generated on a different platform, you may need to run `uv lock` first to regenerate it for your environment.

Database connection errors at startup indicate a problem with `FLYDESK_DATABASE_URL`. In development mode, the default SQLite URL creates a file in the current working directory. If the application does not have write permissions to that directory, the connection will fail. For PostgreSQL, verify that the database server is running, the database exists, and the credentials in the URL are correct. The application logs the connection URL (with the password redacted) on startup, so check the console output for the exact URL being used.

## Frontend Cannot Reach the API

When the frontend displays connection errors or shows empty data, the issue is typically a CORS misconfiguration or a network connectivity problem. The backend must include the frontend's origin in the `FLYDESK_CORS_ORIGINS` list. The default value includes both `http://localhost:3000` and `http://localhost:5173`, which covers the standard SvelteKit development server port.

Verify that the backend is actually running on the expected port. The default is port 8000. If you started uvicorn without specifying `--port 8000`, it may be running on a different port. Check the uvicorn startup output for the actual address and port.

If both the backend and frontend are running but requests still fail, check your browser's developer console for specific CORS error messages. The most common issue is that the frontend origin URL does not exactly match an entry in `FLYDESK_CORS_ORIGINS`. The match is exact and includes the protocol, hostname, and port. `http://localhost:5173` is not the same as `http://127.0.0.1:5173`.

## OIDC Authentication Failures

### Callback Redirect Mismatch

OIDC callback failures occur when the redirect URI configured in Firefly Desk does not exactly match the redirect URI registered with your identity provider. Both values must be identical, including trailing slashes. Check `FLYDESK_OIDC_REDIRECT_URI` and compare it character-by-character with the redirect URI in your OIDC provider's client configuration.

### Missing Roles or Permissions

If the callback succeeds but the user has no roles or permissions, verify that `FLYDESK_OIDC_ROLES_CLAIM` and `FLYDESK_OIDC_PERMISSIONS_CLAIM` point to the correct fields in your provider's JWT tokens. You can decode a token at jwt.io to inspect its claims and find the correct paths.

Common claim paths by provider:

| Provider | Roles Claim | Notes |
|----------|-------------|-------|
| Keycloak | `realm_access.roles` | Nested under realm_access object |
| Auth0 | `https://your-domain.com/roles` | Custom namespace required |
| Microsoft Entra ID | `roles` | Top-level claim, requires app role assignment |
| Okta | `groups` | Uses groups rather than roles by default |
| Google | -- | Does not provide roles natively; use groups or custom claims |
| Cognito | `cognito:groups` | Uses Cognito groups |

### Issuer URL Unreachable

If the OIDC issuer URL is unreachable, the application will fail to start because it needs to fetch the provider's discovery document during initialization. Ensure that the `FLYDESK_OIDC_ISSUER_URL` is accessible from the machine running the backend, including through any firewalls or network policies.

### Token Expiration and Refresh

If users are unexpectedly logged out, verify that the OIDC provider's token expiration settings are reasonable. Short-lived access tokens (under 5 minutes) combined with refresh token issues can cause frequent session drops. Check the provider's token lifetime configuration and ensure refresh tokens are enabled.

## SSO Provider Configuration

### Keycloak

- Ensure the realm name in the issuer URL is correct. The URL format is `https://host/realms/{realm-name}`.
- Verify the client is configured as "confidential" with "Service accounts enabled" if using client credentials.
- Check that the "roles" scope is assigned to the client and that realm roles are mapped to the token.

### Microsoft Entra ID

- The issuer URL format is `https://login.microsoftonline.com/{tenant-id}/v2.0`.
- Set `FLYDESK_OIDC_TENANT_ID` to your Azure AD tenant ID.
- App roles must be defined in the app registration and assigned to users. Group claims alone are not sufficient unless the `FLYDESK_OIDC_ROLES_CLAIM` is set to `groups`.

### Auth0

- The issuer URL is `https://{your-domain}.auth0.com/`.
- Roles must be added to tokens via Auth0 Rules, Actions, or the Authorization Extension. Auth0 does not include roles in tokens by default.
- The roles claim must use a namespaced key like `https://your-app.com/roles`.

### Google

- Google OIDC does not natively support role claims. Use Google Workspace groups and map them to roles through a custom claim or middleware.
- The issuer URL is `https://accounts.google.com`.

### Amazon Cognito

- The issuer URL format is `https://cognito-idp.{region}.amazonaws.com/{user-pool-id}`.
- Roles are typically mapped from Cognito groups using `cognito:groups` as the claim.

### Okta

- The issuer URL is `https://{your-domain}.okta.com/oauth2/default` (or a custom authorization server).
- Ensure the groups claim is included in the ID token by adding a Groups claim to the authorization server.

## Database Migration Errors

Firefly Desk creates all database tables and indexes during application startup using SQLAlchemy's `create_all` mechanism. If you see errors about missing tables or columns, it typically means the startup sequence was interrupted before table creation completed. Restarting the application usually resolves this.

For PostgreSQL deployments, ensure the pgvector extension is installed before starting the application. If the extension is missing, the application will fail when attempting to create vector columns. Connect to the database and run `CREATE EXTENSION IF NOT EXISTS vector;` to install it.

## Seed Data Issues

If the banking seed scenario fails or produces incomplete data, the cleanest resolution is to remove and re-seed:

```bash
flydesk-seed banking --remove
flydesk-seed banking
```

The remove command identifies seed data by its metadata tags, so it only deletes data that was created by the seeding process. Manually created systems, endpoints, and documents are unaffected. If the seed command itself fails, check the console output for specific error messages. The most common cause is a database connection issue.

## Widget Rendering Problems

If the agent's response mentions structured data but the frontend displays it as raw text instead of a rendered widget, the widget directive format may be malformed. The correct format requires the opening fence `:::widget{type="..." panel=true}`, a JSON body on its own line, and a closing fence `:::` on its own line. Missing closing fences, invalid JSON, or unsupported widget types will cause the parser to skip the directive and pass it through as plain text.

Check the browser's developer console for any parsing errors emitted by the widget rendering component. If the directive format is correct but rendering still fails, verify that the widget type specified in the directive matches one of the supported widget types registered in the frontend's widget registry. The supported types are: `status-badge`, `entity-card`, `data-table`, `confirmation`, `key-value`, `alert`, `diff-viewer`, `timeline`, `export`, and `safety-plan`.

## Export Issues

### Export Stuck in "Generating" Status

If an export remains in the "generating" status indefinitely, it likely encountered an error during file generation. Check the backend logs for export-related error messages. The most common cause is malformed source data that does not match the expected table format (`{"columns": [...], "rows": [...]}`).

### PDF Generation Falls Back to HTML

PDF generation requires the `weasyprint` library, which depends on system-level libraries (Cairo, Pango, GDK-PixBuf). If these are not installed, the export service falls back to generating an HTML file instead. Install the system dependencies for weasyprint to enable true PDF output:

- **macOS:** `brew install pango`
- **Ubuntu/Debian:** `apt-get install libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf2.0-0`

### Export File Not Found on Download

If a completed export returns a 404 on download, verify that the `FLYDESK_FILE_STORAGE_PATH` directory exists and is writable. Also check that the path is consistent between the process that generated the export and the process serving the download request. In multi-instance deployments, all instances must have access to the same file storage.

### Export Template Column Mapping Not Applied

Templates only map columns that exactly match the column names in the source data. If the template's `column_mapping` keys do not match the source data's column headers, the mapping is silently skipped. Verify that the column names in your template match the column names in the data being exported.

## Knowledge Base Issues

### Documents Not Appearing in Search Results

If a document was added successfully but does not appear in the agent's responses, verify that the document was indexed. Check the document's chunk count in the admin interface. A chunk count of zero indicates that indexing failed, usually because the embedding provider was not configured or returned an error.

In development mode, the no-op embedding provider is used, which means all documents receive zero vectors and similarity search will not produce meaningful results. This is expected in development mode, where the focus is on API correctness rather than semantic retrieval quality.

### URL Import Fails

URL import failures are typically caused by network issues (the URL is unreachable from the server), SSL certificate problems, or the target server blocking automated requests. The importer follows redirects automatically but has a reasonable timeout. Check the backend logs for the specific HTTP error.

If the URL returns content that is not HTML, JSON, or YAML, the importer stores the raw text content as-is. Binary formats (PDF, Word, images) are not supported through URL import; use file upload instead.

### Knowledge Graph Entities Missing Relationships

If the graph explorer shows entities without connections, the relationships may not have been created. Relationships must be explicitly created through the API; they are not automatically inferred from document content. Use `POST /api/knowledge/graph/relationships` to create connections between entities.

## RBAC Issues

### User Cannot Access Expected Features

If a user reports missing functionality, verify their role assignments. The most common cause is a role that does not include the necessary permissions. Use the Role Manager in the admin console to inspect the permissions assigned to the user's role.

The three built-in roles provide the following access levels:

- **Administrator:** Full access to all features (wildcard `*` permission).
- **Operator:** Operational access to catalog (read, write), knowledge (read), exports (create, download), chat, and audit.
- **Viewer:** Read-only access to knowledge, catalog, and chat.

### Permission Denied Despite Correct Role

If a user has the correct role but still receives permission errors, check whether the OIDC roles claim is being parsed correctly. The claim path must exactly match the structure of the JWT token. Use the `/api/auth/me` endpoint to verify what roles and permissions the system has extracted from the user's token.

### Custom Roles Not Taking Effect

After creating or modifying a custom role, the user must start a new session (log out and log back in) for the role changes to take effect. Existing sessions retain the permissions that were present at the time of authentication.

## File Upload Issues

### Upload Rejected with Size Error

The default maximum file size is 50 MB, controlled by `FLYDESK_FILE_MAX_SIZE_MB`. If users need to upload larger files, increase this limit. Note that very large files may cause memory pressure during content extraction.

### Content Extraction Returns Empty Text

Content extraction is supported for text-based formats (plain text, markdown, HTML, JSON, YAML). Binary formats such as PDF, Word documents, and images are stored but their content is not automatically extracted. The file is still available for download and can be referenced in conversations.

### Upload Directory Permission Errors

Ensure the `FLYDESK_FILE_STORAGE_PATH` directory exists and the application process has write permissions. In containerized deployments, this often requires mounting a volume with appropriate permissions.

```bash
# Create the upload directory with correct permissions
mkdir -p /data/flydesk/uploads
chown -R appuser:appgroup /data/flydesk/uploads
```
