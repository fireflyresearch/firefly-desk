---
type: tutorial
---

# Dev Tools

Dev Tools are development-mode utilities for debugging webhook delivery and testing integrations locally. Access them from the admin console under **Dev Tools**.

## Webhook Log

The webhook log records every inbound webhook request received by your Firefly Desk instance. Each entry captures:

- **Provider** -- Which email provider sent the webhook (Resend, SES, SendGrid).
- **From** -- The sender's email address.
- **Subject** -- The email subject line.
- **Status** -- Processing result (success, failed, dropped).
- **Duration** -- How long the webhook took to process.

### Features

- **Auto-refresh** -- Toggle auto-refresh to see new entries appear in real time as webhooks arrive.
- **Expandable payload** -- Click any entry to view the full raw webhook payload for debugging.
- **Clear** -- Remove all log entries to start fresh.

## Tunnel

The tunnel feature exposes your local Firefly Desk instance via a public HTTPS URL so email providers can deliver webhooks to your development machine.

## Tunnel Setup: ngrok

[ngrok](https://ngrok.com) is the recommended tunnel backend. It requires a free account and auth token.

1. Sign up at [ngrok.com](https://ngrok.com) and copy your auth token.
2. In the Dev Tools panel, paste your ngrok auth token and save it.
3. If `pyngrok` is not installed, click the **Install pyngrok** button for one-click installation.
4. Click **Start Tunnel** to open a public HTTPS tunnel to your local server.
5. Copy the displayed webhook URL and paste it into your email provider's webhook configuration.
6. Click **Stop Tunnel** when you're done testing.

## Tunnel Setup: cloudflared

[cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) is a zero-configuration alternative that requires no account. If `cloudflared` is installed and available on your PATH, it appears as a tunnel backend option automatically.

## Integration Discovery

When a tunnel is active, Dev Tools automatically detects the webhook paths for your configured email provider and displays them with the full tunnel URL. This makes it easy to copy the correct URL into your provider's webhook settings without guessing the path format.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/dev-tools/log` | List webhook log entries. |
| `GET` | `/api/dev-tools/log/{id}` | Get a single entry with full payload. |
| `DELETE` | `/api/dev-tools/log` | Clear all log entries. |
| `GET` | `/api/dev-tools/tunnel/status` | Current tunnel status. |
| `POST` | `/api/dev-tools/tunnel/start` | Start a tunnel. |
| `POST` | `/api/dev-tools/tunnel/stop` | Stop the active tunnel. |
| `GET` | `/api/dev-tools/tunnel/backends` | List available tunnel backends. |
| `GET` | `/api/dev-tools/tunnel/pyngrok-status` | Check if pyngrok is installed. |
| `POST` | `/api/dev-tools/tunnel/install-pyngrok` | Install pyngrok. |
| `PUT` | `/api/dev-tools/tunnel/auth-token` | Save ngrok auth token. |
| `GET` | `/api/dev-tools/integrations` | List detected integrations with webhook paths. |

## Tips

- Use auto-refresh when testing live webhook delivery — entries appear as they arrive.
- The tunnel URL changes on each restart, so update your provider's webhook configuration accordingly.
- Keep the Dev Tools page open while testing inbound email to monitor the webhook log in real time.
- The tunnel feature is only available in dev mode and is intentionally disabled in production.
