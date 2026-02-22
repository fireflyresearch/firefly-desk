# Firefly Desk Frontend

The Firefly Desk frontend is a SvelteKit application built with Svelte 5 (runes) and Tailwind CSS 4. It provides the conversational interface, admin console, and all user-facing components for the platform.

## Architecture

### Framework

The frontend uses SvelteKit for routing and server-side rendering, with Svelte 5's runes-based reactivity system (`$state`, `$derived`, `$effect`). All components use Svelte 5 syntax.

### Styling

Tailwind CSS 4 is used for all styling, integrated via the `@tailwindcss/vite` plugin. The `@tailwindcss/typography` plugin provides prose styling for rendered markdown content. Theming is driven by CSS custom properties, allowing the accent color and other branding values to be set dynamically from backend configuration.

### Routing

SvelteKit's file-based routing is organized into three route groups:

- `(app)/` -- The main application shell with the sidebar, chat interface, and admin pages. Protected by authentication in production mode.
- `auth/` -- Authentication routes including login and OIDC callback.
- `setup/` -- Initial setup and onboarding wizard.

### Dependencies

| Package | Purpose |
|---------|---------|
| `svelte` 5.x | Component framework with runes reactivity |
| `@sveltejs/kit` | Application framework, routing, and SSR |
| `tailwindcss` 4.x | Utility-first CSS |
| `@tailwindcss/typography` | Prose styling for markdown content |
| `lucide-svelte` | Icon library |
| `marked` | Markdown-to-HTML rendering |
| `dompurify` | HTML sanitization for rendered markdown |
| `d3-force`, `d3-selection` | Force-directed graph visualization |
| `@fontsource/inter` | Primary UI font |
| `@fontsource/jetbrains-mono` | Monospace font for code blocks |

## Component Structure

Components are organized by domain under `src/lib/components/`:

### `layout/`

Application-level layout components:

- **AppShell.svelte** -- The main application layout with sidebar navigation, top bar, and content area.
- **ResizableSplit.svelte** -- A resizable split-pane layout used for the chat interface with side panels.
- **TopBar.svelte** -- The application header with branding, user menu, and navigation controls.

### `chat/`

Conversational interface components:

- **ChatContainer.svelte** -- The main chat view that orchestrates message display, input, and SSE streaming. Handles tool execution events, confirmation flows, and widget rendering.
- **InputBar.svelte** -- The message input area with file upload support and send controls.
- **MessageBubble.svelte** -- Individual message rendering with role-based styling (user vs. assistant).
- **StreamingMessage.svelte** -- Handles real-time token streaming during agent responses.
- **MarkdownContent.svelte** -- Renders markdown content with sanitized HTML using Marked and DOMPurify.
- **WidgetSlot.svelte** -- Resolves widget directives to their Svelte components using the widget registry.
- **ConversationList.svelte** -- Sidebar list of conversations with create and delete functionality.
- **EmberAvatar.svelte** -- The agent's avatar component.
- **ChatEmptyState.svelte** -- Displayed when a conversation has no messages.
- **ThinkingIndicator.svelte** -- Visual indicator while the agent is processing.
- **ToolProgress.svelte** -- Displays tool execution progress during agent turns.
- **ToolSummary.svelte** -- Summary of completed tool executions.
- **FileUploadArea.svelte** -- File upload interface within the input area.
- **DropOverlay.svelte** -- Drag-and-drop overlay for file uploads.

### `admin/`

Admin console components:

- **AdminDashboard.svelte** -- Platform overview with aggregated statistics.
- **CatalogManager.svelte** -- External system and endpoint management.
- **CredentialVault.svelte** -- Encrypted credential management.
- **KnowledgeBaseManager.svelte** -- Tabbed interface for document management (Documents, Add Document, Graph Explorer).
- **KnowledgeAddDocument.svelte** -- Document creation with manual, URL import, and file upload methods.
- **KnowledgeDocumentDetail.svelte** -- Detailed document view with metadata and content.
- **KnowledgeGraphExplorer.svelte** -- Interactive D3 force-directed graph visualization of knowledge entities.
- **RoleManager.svelte** -- RBAC role viewing and management.
- **UserManager.svelte** -- User account management with role assignment.
- **ExportManager.svelte** -- Export viewing, downloading, and template management.
- **SSOManager.svelte** -- OIDC provider configuration.
- **LLMProviderManager.svelte** -- LLM provider API key management.
- **AuditViewer.svelte** -- Searchable audit trail interface.

### `widgets/`

Chat widget components rendered from agent directives:

- **DataTable.svelte** -- Tabular data display with column headers and rows.
- **EntityCard.svelte** -- Structured entity information card.
- **StatusBadge.svelte** -- Status indicator with color coding.
- **KeyValueList.svelte** -- Key-value pair display.
- **AlertBanner.svelte** -- Alert and notification banners.
- **DiffViewer.svelte** -- Before/after comparison display.
- **Timeline.svelte** -- Chronological event timeline.
- **ConfirmationCard.svelte** -- Safety confirmation prompt for high-risk operations.
- **SafetyPlanCard.svelte** -- Multi-step operation safety plan display.
- **ExportCard.svelte** -- Export result with download link.

### `settings/` and `panels/`

Settings page components and side panel components.

## Widget System

The widget system allows the agent to render structured data as interactive components within the chat interface. Widgets are defined by directives in the agent's response text.

### Widget Registry

The widget registry (`src/lib/widgets/registry.ts`) maps widget type strings to their Svelte components:

```typescript
export const widgetRegistry: Record<string, Component> = {
    'status-badge': StatusBadge,
    'entity-card': EntityCard,
    'data-table': DataTable,
    'confirmation': ConfirmationCard,
    'key-value': KeyValueList,
    'alert': AlertBanner,
    'diff-viewer': DiffViewer,
    'timeline': Timeline,
    'export': ExportCard,
    'safety-plan': SafetyPlanCard
};
```

### Directive Format

The agent produces widget directives in this format:

```
:::widget{type="data-table" panel=true}
{"columns": ["Name", "Amount"], "rows": [["Alice", "$500"]]}
:::
```

The WidgetSlot component resolves the type string to a component via the registry and passes the JSON payload as props.

## Store Patterns

Stores are located in `src/lib/stores/` and use Svelte's `writable` and `derived` stores:

- **chat.ts** -- Conversation list, active conversation, messages, and streaming state. Includes async initialization for loading conversations from the API.
- **panel.ts** -- Side panel state (open/closed, content).
- **user.ts** -- Authenticated user profile, roles, and permissions.
- **sidebar.ts** -- Sidebar navigation state.
- **theme.ts** -- Theme preferences (light/dark mode).
- **tools.ts** -- Tool execution state during agent turns.
- **settings.ts** -- Application settings loaded from the backend.

### Async Initialization Pattern

Stores that need to load initial data from the API use an async initialization pattern:

```typescript
export const conversations = writable<Conversation[]>([]);

export async function initConversations() {
    const data = await apiFetchConversations();
    conversations.set(data);
}
```

This pattern separates store creation (synchronous) from data loading (async), allowing components to subscribe immediately while data loads in the background.

## Services

Services are located in `src/lib/services/` and provide API communication:

- **api.ts** -- Base HTTP client with authentication headers and error handling.
- **auth.ts** -- Authentication flow (login, logout, session management).
- **chat.ts** -- Chat message sending with SSE stream handling.
- **conversations.ts** -- Conversation CRUD operations.
- **files.ts** -- File upload and download.
- **sse.ts** -- Server-Sent Events client for streaming responses.

## Development Workflow

### Prerequisites

- Node.js 20 or later
- The backend server running on port 8000

### Install Dependencies

```bash
npm install
```

### Start Development Server

```bash
npm run dev
```

The development server starts at `http://localhost:5173` and proxies API requests to the backend on port 8000. Hot module replacement is enabled for rapid iteration.

### Build for Production

```bash
npm run build
```

Creates an optimized production build in the `build/` directory.

### Preview Production Build

```bash
npm run preview
```

### Type Checking

```bash
npm run check
```

Runs `svelte-check` for TypeScript type validation across all components and modules.

## Environment Configuration

The frontend reads its configuration from the backend API at runtime. No environment variables are required for the frontend itself. The backend's `FLYDEK_APP_TITLE`, `FLYDEK_APP_LOGO_URL`, and `FLYDEK_ACCENT_COLOR` values are fetched and applied as CSS custom properties.

The Vite configuration proxies `/api` requests to the backend during development. This is configured in `vite.config.ts` and requires no manual setup.

## Naming Conventions

- **Components:** PascalCase (e.g., `ChatContainer.svelte`, `DataTable.svelte`)
- **Stores:** camelCase files with exported writable stores (e.g., `chat.ts` exports `conversations`, `messages`)
- **Services:** camelCase files with exported async functions (e.g., `api.ts` exports `fetchJSON`, `postJSON`)
- **Routes:** Lowercase directory names following SvelteKit conventions

## License

Copyright 2026 Firefly Software Solutions Inc. Licensed under the Apache License, Version 2.0.
