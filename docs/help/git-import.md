# Git Import

Git Import lets you pull documentation directly from Git repositories into the Firefly Desk knowledge base. This is useful for keeping your agent's knowledge in sync with documentation that lives alongside your code.

## Supported Providers

Firefly Desk uses a unified Git provider abstraction that supports:

- **GitHub** -- Fully supported. Connects via OAuth or personal access token (PAT).
- **GitLab** -- Planned. Will use the same provider interface.
- **Bitbucket** -- Planned. Will use the same provider interface.

Each provider implements the same interface: validate tokens, list accounts/organizations, browse repositories, list branches, walk file trees, and fetch file content.

## Setting Up GitHub OAuth

To enable users to connect their GitHub accounts:

1. Create a GitHub OAuth App at **GitHub > Settings > Developer Settings > OAuth Apps**.
2. Set the authorization callback URL to your Firefly Desk instance's callback endpoint.
3. Copy the **Client ID** and **Client Secret**.
4. In the admin console, go to **Git Providers** and add a new GitHub provider with these credentials.

Alternatively, users can authenticate with a personal access token (PAT) that has `repo` scope.

## Importing Files

Once authenticated with a Git provider:

1. **Browse repositories** -- List your personal repos or organization repos.
2. **Select a branch** -- Choose the branch to import from (defaults to the repo's default branch).
3. **Browse the file tree** -- The system shows importable files filtered by extension: `.md`, `.json`, `.yaml`, and `.yml`.
4. **Select files** -- Pick individual files or select multiple files for batch import.
5. **Import** -- Selected files are fetched, their content is decoded, and each file is indexed into the knowledge base as a document.

The system automatically detects document types (tutorial, reference, API spec, etc.) based on content analysis.

## Multi-Repo Import

You can import from multiple repositories in a single session. Browse and select files across different repos, then import them all at once. Each imported document tracks its source repository and file path in metadata.

## Re-importing

When documentation changes in your repository, re-import the same files to update the knowledge base. The indexer processes the updated content, re-chunks, and re-embeds it.

## Tips

- Use a dedicated service account token for organization-wide imports rather than personal tokens.
- Import only documentation files -- the extension filter (`.md`, `.json`, `.yaml`, `.yml`) prevents accidental code imports.
- Tag imported documents with the repository name for easy identification and management.
- Check the knowledge base after import to verify document types were correctly detected.
