# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Banking skill seed data.

Provides five pre-configured skills that reference the banking service
endpoints and knowledge documents seeded by :mod:`flydesk.seeds.banking`.
"""

from __future__ import annotations

from flydesk.skills.models import Skill

# ---------------------------------------------------------------------------
# Account Lookup
# ---------------------------------------------------------------------------

SKILL_ACCOUNT_LOOKUP = Skill(
    id="skill-account-lookup",
    name="Account Lookup",
    description=(
        "Look up customer account details by ID or search criteria."
    ),
    content=(
        "# Account Lookup\n\n"
        "Use this skill when a customer or agent needs to find or review\n"
        "account information.\n\n"
        "## Steps\n\n"
        "1. **Identify the customer.** If you already have a customer ID,\n"
        "   proceed to step 2. Otherwise, use the **Search Customers**\n"
        "   endpoint (`ep-search-customers`) to locate the customer by\n"
        "   name, email, phone number, or account number.\n"
        "2. **Retrieve the profile.** Call the **Get Customer Profile**\n"
        "   endpoint (`ep-get-customer-profile`) with the customer ID.\n"
        "   Set `include_accounts=true` to embed linked account summaries.\n"
        "3. **Present the results.** Summarize key details for the caller:\n"
        "   full name, email, phone, KYC status, and a list of linked\n"
        "   accounts with their balances.\n\n"
        "## Guidelines\n\n"
        "- Always verify the customer's identity before sharing account\n"
        "  details (see Compliance Guidelines, `doc-compliance-guidelines`).\n"
        "- Mask the full SSN -- display only the last four digits.\n"
        "- If no results are found, ask the customer to confirm the search\n"
        "  criteria and try alternative identifiers.\n\n"
        "## Referenced Endpoints\n\n"
        "- `ep-get-customer-profile` -- Get Customer Profile\n"
        "- `ep-search-customers` -- Search Customers\n"
    ),
    tags=["customers", "accounts", "lookup", "read"],
    active=True,
)

# ---------------------------------------------------------------------------
# Transaction History
# ---------------------------------------------------------------------------

SKILL_TRANSACTION_HISTORY = Skill(
    id="skill-transaction-history",
    name="Transaction History",
    description=(
        "Retrieve recent transactions for a customer account."
    ),
    content=(
        "# Transaction History\n\n"
        "Use this skill when a customer asks about recent transactions,\n"
        "wants to verify a charge, or needs a statement for a specific\n"
        "period.\n\n"
        "## Steps\n\n"
        "1. **Identify the account.** Confirm the account ID with the\n"
        "   customer. If unknown, perform an Account Lookup first.\n"
        "2. **Determine the date range.** Ask the customer for the time\n"
        "   period they are interested in. Default to the last 30 days if\n"
        "   unspecified.\n"
        "3. **Retrieve transactions.** Call the **Get Transactions**\n"
        "   endpoint (`ep-get-transactions`) with the account ID, start\n"
        "   date, and end date. Optionally filter by transaction type.\n"
        "4. **Offer a statement.** If the customer needs a formal summary,\n"
        "   use the **Get Statement** endpoint (`ep-get-statement`) for\n"
        "   the relevant period in `YYYY-MM` format.\n"
        "5. **Present the results.** List the transactions with date,\n"
        "   description, amount, and running balance. Highlight any\n"
        "   transactions the customer specifically asked about.\n\n"
        "## Guidelines\n\n"
        "- Always authenticate the customer before sharing transaction\n"
        "  data (at least single-factor for read-only lookups).\n"
        "- Do not disclose account numbers in full -- mask to the last\n"
        "  four digits.\n"
        "- If the customer disputes a transaction, transition to the\n"
        "  Refund Processing skill.\n\n"
        "## Referenced Endpoints\n\n"
        "- `ep-get-transactions` -- Get Transactions\n"
        "- `ep-get-statement` -- Get Statement\n"
    ),
    tags=["transactions", "statements", "history", "read"],
    active=True,
)

# ---------------------------------------------------------------------------
# Refund Processing
# ---------------------------------------------------------------------------

SKILL_REFUND_PROCESSING = Skill(
    id="skill-refund-processing",
    name="Refund Processing",
    description=(
        "Guide through the refund workflow with policy compliance."
    ),
    content=(
        "# Refund Processing\n\n"
        "Use this skill when a customer requests a refund for a disputed\n"
        "or erroneous transaction.\n\n"
        "## Steps\n\n"
        "1. **Verify the transaction.** Retrieve the transaction using\n"
        "   the Transaction History skill to confirm it exists and review\n"
        "   the amount, date, and merchant.\n"
        "2. **Review the Refund Policy.** Consult the Refund Policy\n"
        "   document (`doc-refund-policy`) to confirm eligibility:\n"
        "   - The transaction must be within the past 90 days.\n"
        "   - Identify the correct reason code: `duplicate_charge`,\n"
        "     `merchant_error`, `service_issue`, or `goodwill`.\n"
        "   - Check refund limits: up to $100 auto-approved, $100-$1000\n"
        "     requires supervisor approval, over $1000 requires director\n"
        "     approval.\n"
        "   - Goodwill credits are limited to $50 per incident.\n"
        "3. **Confirm with the customer.** State the refund amount,\n"
        "   reason, and estimated timeline before proceeding.\n"
        "4. **Initiate the refund.** Call the **Initiate Refund** endpoint\n"
        "   (`ep-initiate-refund`) with the transaction ID, amount,\n"
        "   reason, and reason code.\n"
        "5. **Communicate the outcome.** Inform the customer of the\n"
        "   refund status (approved, pending_approval, or rejected) and\n"
        "   the estimated completion date.\n"
        "6. **Create a ticket.** If the refund requires further follow-up\n"
        "   (e.g., supervisor approval), create a support ticket to track\n"
        "   it.\n\n"
        "## Guidelines\n\n"
        "- Never exceed your daily refund limit of $2,500.\n"
        "- Document the reason thoroughly -- all refunds are audited.\n"
        "- If the customer is dissatisfied with the outcome, escalate to\n"
        "  a supervisor rather than issuing an unauthorized refund.\n\n"
        "## Referenced Endpoints\n\n"
        "- `ep-initiate-refund` -- Initiate Refund\n\n"
        "## Referenced Documents\n\n"
        "- `doc-refund-policy` -- Refund Policy\n"
    ),
    tags=["refunds", "transactions", "disputes", "write"],
    active=True,
)

# ---------------------------------------------------------------------------
# Ticket Management
# ---------------------------------------------------------------------------

SKILL_TICKET_MANAGEMENT = Skill(
    id="skill-ticket-management",
    name="Ticket Management",
    description=(
        "Create, search, and manage support tickets."
    ),
    content=(
        "# Ticket Management\n\n"
        "Use this skill to create new support tickets, check the status\n"
        "of existing tickets, or close resolved tickets.\n\n"
        "## Steps\n\n"
        "### Searching Existing Tickets\n\n"
        "1. Call the **List Tickets** endpoint (`ep-list-tickets`) with\n"
        "   the customer ID. Optionally filter by status (open,\n"
        "   in_progress, resolved, closed).\n"
        "2. Present a summary of matching tickets including ticket ID,\n"
        "   subject, status, priority, and creation date.\n\n"
        "### Creating a New Ticket\n\n"
        "1. **Check for duplicates.** Always search for existing open\n"
        "   tickets before creating a new one.\n"
        "2. **Gather details.** Collect the customer ID, a concise\n"
        "   subject, a detailed description, the issue category\n"
        "   (account_inquiry, transaction_dispute, technical_issue,\n"
        "   product_question, complaint, other), and priority (low,\n"
        "   medium, high, critical).\n"
        "3. **Create the ticket.** Call the **Create Ticket** endpoint\n"
        "   (`ep-create-ticket`) with the gathered details.\n"
        "4. **Confirm with the customer.** Share the assigned ticket ID\n"
        "   and the queue it was routed to.\n\n"
        "### Closing a Ticket\n\n"
        "1. **Verify resolution.** Confirm with the customer that their\n"
        "   issue has been fully resolved.\n"
        "2. **Close the ticket.** Call the **Close Ticket** endpoint\n"
        "   (`ep-close-ticket`) with a resolution summary and the\n"
        "   appropriate resolution code (resolved, duplicate,\n"
        "   no_action_needed, escalated, customer_withdrew).\n\n"
        "## Guidelines\n\n"
        "- Set priority to 'critical' only for fraud, security breaches,\n"
        "  or complete service outages.\n"
        "- Always include enough detail in the description for another\n"
        "  agent to pick up the case without additional context.\n"
        "- After closing a ticket, the customer will receive a\n"
        "  satisfaction survey automatically.\n\n"
        "## Referenced Endpoints\n\n"
        "- `ep-list-tickets` -- List Tickets\n"
        "- `ep-create-ticket` -- Create Ticket\n"
        "- `ep-close-ticket` -- Close Ticket\n"
    ),
    tags=["support", "tickets", "management"],
    active=True,
)

# ---------------------------------------------------------------------------
# Product Recommendations
# ---------------------------------------------------------------------------

SKILL_PRODUCT_RECOMMENDATIONS = Skill(
    id="skill-product-recommendations",
    name="Product Recommendations",
    description=(
        "Suggest suitable banking products based on customer profile."
    ),
    content=(
        "# Product Recommendations\n\n"
        "Use this skill when a customer asks about available products,\n"
        "wants a recommendation, or you identify an upsell opportunity\n"
        "during a support interaction.\n\n"
        "## Steps\n\n"
        "1. **Understand the need.** Ask the customer what they are\n"
        "   looking for: a new checking or savings account, a credit\n"
        "   card, a personal loan, or a mortgage product.\n"
        "2. **Browse the catalog.** Call the **List Products** endpoint\n"
        "   (`ep-list-products`) filtered by the relevant category\n"
        "   (checking, savings, credit_card, loan, mortgage, investment).\n"
        "3. **Get product details.** For each product that may be a good\n"
        "   fit, call the **Get Product Details** endpoint\n"
        "   (`ep-get-product-details`) to retrieve interest rates, fees,\n"
        "   and eligibility criteria.\n"
        "4. **Check eligibility.** If the customer is interested in a\n"
        "   specific product, call the **Check Eligibility** endpoint\n"
        "   (`ep-check-eligibility`) with the customer ID and product ID.\n"
        "5. **Present recommendations.** Summarize the top products with\n"
        "   key features, rates, and fees. If the customer is not\n"
        "   eligible, suggest alternative products returned by the\n"
        "   eligibility check.\n\n"
        "## Guidelines\n\n"
        "- Always retrieve the customer profile first to understand their\n"
        "  existing products and avoid recommending duplicates.\n"
        "- Present options objectively -- do not pressure the customer.\n"
        "- For detailed product questions, refer to the Product FAQ\n"
        "  document (`doc-product-faq`).\n"
        "- Eligibility checks do not affect the customer's credit score.\n\n"
        "## Referenced Endpoints\n\n"
        "- `ep-list-products` -- List Products\n"
        "- `ep-get-product-details` -- Get Product Details\n"
        "- `ep-check-eligibility` -- Check Eligibility\n"
    ),
    tags=["products", "recommendations", "eligibility", "read"],
    active=True,
)

# ---------------------------------------------------------------------------
# Aggregate list for seeding
# ---------------------------------------------------------------------------

SKILLS: list[Skill] = [
    SKILL_ACCOUNT_LOOKUP,
    SKILL_TRANSACTION_HISTORY,
    SKILL_REFUND_PROCESSING,
    SKILL_TICKET_MANAGEMENT,
    SKILL_PRODUCT_RECOMMENDATIONS,
]
