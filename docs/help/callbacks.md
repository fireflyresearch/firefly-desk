---
type: tutorial
---

# Callbacks

Callbacks are outbound webhooks that notify external systems when events occur in Firefly Desk. Register an HTTPS endpoint, choose which events to subscribe to, and Firefly Desk will send signed POST requests whenever those events fire.

## How It Works

1. Register one or more callback endpoint URLs in the admin console under **Callbacks**.
2. Select the events each endpoint should receive.
3. When an event fires, Firefly Desk sends an HMAC-signed POST request with a JSON payload describing the event.
4. Your endpoint responds with a 2xx status to acknowledge receipt.

Each callback endpoint has its own auto-generated signing secret, event subscriptions, and enable/disable toggle.

## Events

| Event | Description |
|-------|-------------|
| `email.sent` | An outbound email was successfully delivered through the configured provider. |
| `email.received` | An inbound email was received and matched to a user account. |
| `email.failed` | An outbound email delivery attempt failed. |
| `conversation.created` | A new conversation was started (via chat or inbound email). |
| `conversation.updated` | An existing conversation received a new message or status change. |
| `agent.error` | The agent encountered an error during processing (e.g., LLM failure, tool execution error). |

## Managing Endpoints

From the admin console, navigate to **Callbacks** to manage your webhook endpoints.

- **Add Callback** -- Click "Add Callback" to register a new endpoint. Provide the HTTPS URL and select which events to subscribe to.
- **Edit** -- Update the URL or change event subscriptions for an existing endpoint.
- **Enable / Disable** -- Toggle an endpoint on or off without deleting it. Disabled endpoints stop receiving events but retain their configuration.
- **Delete** -- Permanently remove a callback endpoint and its delivery history.
- **Test** -- Send a test payload to verify your endpoint is reachable and responding correctly.

## Signing & Verification

Every callback request is signed using HMAC-SHA256 with the endpoint's auto-generated secret. Two custom headers are included with each request:

- `X-Flydesk-Signature` -- The HMAC-SHA256 hex digest of the request body, computed with the endpoint's signing secret.
- `X-Flydesk-Event` -- The event type (e.g., `email.sent`).

### Verification Example (Python)

```python
import hashlib
import hmac

def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

The signing secret is displayed once when the endpoint is created and can be regenerated from the endpoint detail page.

## Delivery & Retries

Callback delivery is fire-and-forget via `asyncio.create_task` — it does not block the operation that triggered the event. If the initial delivery fails, exponential backoff retries are attempted:

| Attempt | Delay |
|---------|-------|
| 1st | Immediate |
| 2nd | 30 seconds |
| 3rd | 5 minutes |

After all retries are exhausted, the delivery is marked as failed in the delivery log.

The **Delivery Log** tab on each callback endpoint shows recent deliveries with:

- Event type and timestamp
- HTTP status code
- Response duration
- Success or failure status

You can filter the delivery log by status or event type.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/callbacks` | List all callback configurations. |
| `POST` | `/api/callbacks` | Create a new callback endpoint. |
| `PUT` | `/api/callbacks/{id}` | Update a callback configuration. |
| `DELETE` | `/api/callbacks/{id}` | Remove a callback endpoint. |
| `POST` | `/api/callbacks/{id}/test` | Send a test payload to the endpoint. |
| `GET` | `/api/callbacks/delivery-log` | Query delivery history across all endpoints. |

## Troubleshooting

### Unreachable URL

**Symptom:** Deliveries fail with a connection error.

**Resolution:** Ensure the callback URL is publicly reachable over HTTPS. For local development, use a tunnel (see [Dev Tools](dev-tools.md)). Check that your firewall allows inbound connections on the target port.

### Invalid Signature Verification

**Symptom:** Your endpoint rejects the signature as invalid.

**Resolution:** Verify you are using the correct signing secret for this endpoint. Ensure you are computing HMAC-SHA256 over the raw request body (not parsed JSON). Compare the hex digest against the `X-Flydesk-Signature` header value.

### Retries Exhausted

**Symptom:** Delivery log shows "failed" after 3 attempts.

**Resolution:** Check your endpoint's availability and response times. Endpoints must respond within 10 seconds. Review your server logs for errors. Re-enable the endpoint and send a test payload to verify connectivity.

### Callback Disabled

**Symptom:** Events are not being delivered even though the endpoint exists.

**Resolution:** Check the endpoint's enabled/disabled toggle in the admin console. Endpoints are automatically disabled after repeated failures to prevent unnecessary retries.

## Tips

- Use [webhook.site](https://webhook.site) or a similar service to test callbacks before connecting a production endpoint.
- Subscribe to all events initially to understand the payload structure, then narrow down to the events you need.
- Monitor the delivery log regularly to catch failures early.
- Rotate signing secrets periodically and update your verification code accordingly.
