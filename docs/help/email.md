---
type: tutorial
---

# Email Channel

The email channel extends Firefly Desk beyond chat by allowing the AI agent to send and receive emails through standard email infrastructure. Users can email the agent directly, and the agent can compose and send emails as part of its workflow. All email activity flows through the same conversation model used by chat, so messages are threaded, audited, and subject to the same RBAC policies.

## How It Works

Firefly Desk acts as an email gateway between your users and the AI agent. Outbound emails are sent through a configured provider (Resend or AWS SES). Inbound emails arrive via webhook, are parsed and matched to a user account, and then routed into a conversation thread where the agent can respond automatically or on demand.

The lifecycle of an inbound email:

1. The email provider receives a message addressed to your configured sender address.
2. The provider forwards the raw email to your Firefly Desk webhook endpoint.
3. The identity resolver matches the sender's address to a local user account.
4. The thread tracker maps the email's `Message-ID`, `In-Reply-To`, and `References` headers to an existing conversation or creates a new one.
5. If auto-reply is enabled, the agent generates a response and sends it back through the provider.

Outbound emails follow the reverse path: the agent composes a message, the formatter converts Markdown to email-safe HTML, the configured signature is appended, and the provider delivers the email.

## Provider Setup

Firefly Desk supports two email providers. You configure the provider in the admin console under **Email > Connection**.

### Resend

Resend is the recommended provider for most deployments. Setup requires an API key and a verified sender domain.

1. Create a Resend account at [resend.com](https://resend.com).
2. Add and verify your sending domain in the Resend dashboard.
3. Generate an API key with sending permissions.
4. In the Firefly Desk admin console, select **Resend** as the provider and paste your API key.
5. Click **Validate** to confirm the key is accepted. The validation calls the Resend Domains API (no email is sent).

The validate endpoint is:

```
POST /api/settings/email/validate
```

You can also validate credentials inline during the setup wizard without saving:

```
POST /api/settings/email/validate-credentials
{
  "provider": "resend",
  "api_key": "re_..."
}
```

### AWS SES

For organisations already on AWS, SES provides a cost-effective alternative. The adapter uses `boto3` and supports both explicit credentials and the default AWS credential chain (environment variables, instance profile, etc.).

1. Verify your sender domain or email address in the SES console.
2. If your SES account is in sandbox mode, also verify recipient addresses.
3. Configure the AWS region in the admin console (e.g., `us-east-1`).
4. Ensure the server has access to valid AWS credentials through one of the standard boto3 credential sources.

SES inbound email is received through an SNS topic. Configure an SES receiving rule that publishes to SNS, then point the SNS subscription at your Firefly Desk webhook endpoint.

## Identity Settings

Identity settings control how outbound emails appear to recipients. Configure these in the admin console under **Email > Connection**.

- **From address** -- The email address that appears in the `From` header (e.g., `ember@yourcompany.com`). This address must be verified with your provider.
- **Display name** -- The human-readable name shown alongside the address (e.g., `Ember`). Defaults to the agent's configured display name.
- **Reply-to** -- An optional address that overrides where replies are directed. Leave blank to use the from address.

These values are stored in the `EmailSettings` model:

```python
from_address: str = "ember@flydesk.ai"
from_display_name: str = "Ember"
reply_to: str = ""
```

### Domain Verification

Both Resend and SES require domain or address verification before you can send email. Verification proves you own the domain and prevents spoofing. The process varies by provider:

- **Resend:** Add DNS records (DKIM, SPF, DMARC) in your domain registrar. The Resend dashboard shows the exact records to add and tracks verification status.
- **SES:** Verify the domain or individual email address in the SES console. SES provides DKIM CNAME records to add to your DNS.

Until verification completes, sending attempts will fail with a 403 or "sender not verified" error.

## Signatures

The signature editor lets you customise the HTML block appended to every outgoing email. Access it from the **Email > Signature** tab in the admin console.

### Default Signature

When no custom signature has been saved, Firefly Desk generates a branded default signature using the agent's display name, from address, and the Flydesk logo. The default signature uses `<table>` layout with inline CSS for maximum email client compatibility. It includes:

- A circular logo or avatar initial
- The agent's display name and "AI Assistant" subtitle
- The from address as a clickable `mailto:` link
- The company name ("Firefly Desk")

The default signature is generated on the fly and is not persisted. It appears in the editor as a starting point.

### Custom Signature

Switch to edit mode to modify the signature HTML directly. The editor supports syntax-highlighted HTML editing. The signature preview updates in real time via an iframe that renders the HTML.

### Logo Upload

Upload a custom logo image to replace the default Flydesk logo in the signature. Supported formats are PNG, JPEG, GIF, and WebP. The maximum file size is 2 MB. Uploaded images are stored as base64 data URIs for portability -- they are embedded directly in the email HTML rather than hosted externally, ensuring they display regardless of the recipient's image loading settings.

```
POST /api/settings/email/signature-image
Content-Type: multipart/form-data
```

To remove a custom image and revert to the default logo:

```
DELETE /api/settings/email/signature-image
```

### Reset to Default

Click "Reset to Default" to discard custom edits and regenerate the default signature from current identity settings. This calls:

```
GET /api/settings/email/default-signature
```

The returned HTML reflects the current display name and from address but is not saved until you explicitly click Save.

## Inbound Email

Inbound email allows users to communicate with the AI agent by sending regular emails. The system handles parsing, identity resolution, conversation threading, and optional auto-reply.

### Webhook Setup

Your email provider must be configured to forward inbound emails to a Firefly Desk webhook endpoint. The URL format is:

```
https://your-domain.com/api/email/inbound/{provider}
```

Where `{provider}` is either `resend` or `ses`.

**Resend webhook setup:**

1. Go to the Resend dashboard and navigate to Webhooks.
2. Create a new webhook endpoint.
3. Set the URL to `https://your-domain.com/api/email/inbound/resend`.
4. Save the webhook. Resend will now forward inbound emails to your server.

**SES webhook setup:**

1. In the AWS console, create a Receipt Rule in SES.
2. Create a rule that sends inbound emails to an SNS Topic.
3. Subscribe your Firefly Desk endpoint (`/api/email/inbound/ses`) to the SNS topic via HTTPS.

### Ngrok Tunnel for Development

In dev mode, Firefly Desk includes a built-in ngrok tunnel manager for testing inbound email locally without deploying to a public server. The tunnel exposes your local port 8000 via an HTTPS URL.

Prerequisites:

- Install pyngrok: `pip install 'flydesk[tunnel]'`
- Configure your ngrok auth token: `ngrok config add-authtoken <TOKEN>`
- Enable dev mode in your Firefly Desk configuration

The tunnel can be started and stopped from the admin console UI, or via the API:

```
POST /api/settings/email/tunnel/start
POST /api/settings/email/tunnel/stop
GET  /api/settings/email/tunnel/status
```

Once the tunnel is active, the UI displays the public webhook URL ready to copy into your provider's webhook configuration.

### Identity Resolution

When an inbound email arrives, the identity resolver looks up the sender's email address in the local user table. If no matching user is found, the email is silently dropped and a warning is logged. This prevents unknown senders from creating conversations.

You can verify identity resolution from the admin console:

```
POST /api/settings/email/check-identity
{ "email": "alice@example.com" }
```

The response indicates whether the address resolves to a known user and, if so, which one.

The admin console also provides a list of all users with email addresses configured:

```
GET /api/settings/email/users
```

### Email Threading

The thread tracker maintains a mapping between email `Message-ID` headers and Firefly Desk conversation IDs. When a reply arrives, the tracker checks the `In-Reply-To` header first, then falls back to the `References` header chain. If neither matches an existing conversation, a new conversation is created.

Outbound replies include proper `In-Reply-To` and `References` headers so that email clients group the entire exchange into a single thread.

### Inbound Pipeline Testing

The admin console provides a simulation endpoint for testing the full inbound pipeline without sending a real email:

```
POST /api/settings/email/simulate-inbound
{
  "from_address": "alice@example.com",
  "subject": "Test inbound email",
  "body": "This is a simulated inbound email for testing the pipeline."
}
```

The simulation runs identity resolution, thread creation, and (if enabled) auto-reply, then returns a detailed result showing what happened at each step.

## Behaviour Settings

Behaviour settings control how the agent handles email interactions. Configure these in the admin console under **Email > Behaviour**.

### Auto-Reply

When enabled, the agent automatically generates and sends a reply to every inbound email after a configurable delay. The delay (default: 30 seconds) gives the agent time to process the message and produce a thoughtful response rather than replying instantly.

```python
auto_reply: bool = True
auto_reply_delay_seconds: int = 30
```

### Greeting and Sign-Off

- **Include greeting** -- When enabled, the agent prepends a greeting line (e.g., "Hi Sarah,") to the email body.
- **Include sign-off** -- When enabled, the agent appends the configured signature to the email.

### Max Email Length

Limits the character count of the agent's email responses. Default is 2000 characters. This prevents the agent from generating excessively long emails that recipients are unlikely to read.

### Tone, Personality, and Instructions

The email channel supports dedicated persona overrides that apply only to email interactions, separate from the agent's chat personality:

- **Email tone** -- Overrides the agent's default tone for email responses (e.g., "formal and concise").
- **Email personality** -- Overrides personality traits for email context.
- **Email instructions** -- Free-form instructions appended to the system prompt when composing emails.

When these fields are empty, the agent inherits the global personality and tone configured in the Agent Customization panel.

### CC Modes

The `cc_mode` setting controls how the agent handles CC recipients on inbound emails:

- **respond_all** -- Reply to the sender and include all original CC recipients. This is the default.
- **respond_sender** -- Reply only to the sender, dropping CC recipients from the reply.
- **silent** -- Do not send any reply. The inbound email is still processed and recorded in the conversation, but no outbound email is generated.

Additional CC-specific instructions can be provided in the `cc_instructions` field to guide the agent's behaviour when multiple recipients are involved.

## Agent Email Tool

The `send_email` built-in tool allows the agent to compose and send emails during a conversation. This tool is available to users who hold the `email:send` permission (included in the Administrator and Operator built-in roles).

### Tool Definition

```
Name:        send_email
Risk Level:  low_write
Permission:  email:send
```

Parameters:

| Parameter   | Required | Description                                      |
|-------------|----------|--------------------------------------------------|
| `to`        | Yes      | Recipient email address                          |
| `subject`   | Yes      | Email subject line                               |
| `body`      | Yes      | Email body in Markdown format                    |
| `cc`        | No       | Comma-separated CC addresses                     |
| `reply_to`  | No       | Reply-to address (overrides the default)         |

### How It Works

When the agent calls `send_email`, the tool executor:

1. Loads the current email settings (provider, from address, signature).
2. Converts the Markdown body to email-safe HTML using the `EmailFormatter`.
3. Appends the configured signature.
4. Sends the email through the configured provider adapter.
5. Returns a result with `success`, `message_id`, or an `error` description.

The agent uses this tool when a user explicitly asks to send an email, or when a workflow step requires email notification. Because the risk level is `low_write`, the agent may ask for user confirmation before sending depending on your confirmation policy.

### Test Email

Administrators can send a test email from the admin console to verify that outbound delivery is working:

```
POST /api/settings/email/test
{
  "to": "test@example.com",
  "subject": "Test from Ember",
  "body": "This is a test email from Ember @ Firefly Desk."
}
```

The test email uses the same formatting pipeline as real agent emails, including the signature.

## Troubleshooting

### Invalid API Key

**Symptom:** Validation fails with "Invalid API key" or sending returns a 401 error.

**Resolution:** Verify that the API key is correct and has sending permissions. For Resend, regenerate the key from the Resend dashboard. For SES, check that the IAM credentials have `ses:SendEmail` permission.

### Unverified Sender

**Symptom:** Sending fails with a 403 error or "Sender address not verified."

**Resolution:** Confirm that the from address (or its domain) is verified in your provider's dashboard. DNS propagation for DKIM and SPF records can take up to 48 hours.

### Connection Timeout

**Symptom:** Sending fails with "Connection failed" or timeout errors.

**Resolution:** Check that the server has outbound HTTPS access to the provider API (`api.resend.com` for Resend, `email.{region}.amazonaws.com` for SES). Firewall rules or proxy configurations may be blocking the connection.

### Unknown Sender (Inbound)

**Symptom:** Inbound emails are silently dropped. The log shows "Ignoring inbound email from unknown sender."

**Resolution:** The sender's email address does not match any local user account. Add the sender as a user with their email address, or verify the address with the identity check endpoint.

### Webhook Not Receiving

**Symptom:** Inbound emails are not arriving at Firefly Desk.

**Resolution:** Verify the webhook URL is correct and reachable. For local development, ensure the ngrok tunnel is running. Check the provider's webhook delivery logs for failed attempts. Confirm that your server is listening on the expected port.

### Tunnel Unavailable

**Symptom:** The ngrok tunnel controls are disabled or show "not available."

**Resolution:** Ensure `pyngrok` is installed (`pip install 'flydesk[tunnel]'`), the ngrok auth token is configured, and dev mode is enabled. The tunnel feature is intentionally disabled in production.

### Emails Not Threading

**Symptom:** Replies create new conversations instead of continuing existing ones.

**Resolution:** Verify that the email provider preserves `In-Reply-To` and `References` headers when forwarding webhooks. Some provider configurations strip these headers, breaking thread resolution.

## Tips

- Start by sending a test email to yourself to verify the full pipeline before configuring inbound webhooks.
- Use the inbound simulation endpoint to test identity resolution and threading without sending real emails.
- Keep email instructions focused on email-specific guidance; general agent behaviour belongs in the Agent Customization panel.
- Set a reasonable max email length. Most business emails are under 500 words; 2000 characters is a sensible default.
- If you use the `silent` CC mode, inbound emails are still recorded -- the agent simply does not reply. This is useful for monitoring or logging purposes.
