# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Banking platform seed data for the MVP example domain.

Populates the Service Catalog with five banking systems, fifteen service
endpoints, and five knowledge-base documents that together represent a
realistic retail-banking support desk.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from flydek.catalog.enums import AuthType, HttpMethod, RiskLevel, SystemStatus
from flydek.catalog.models import (
    AuthConfig,
    ExternalSystem,
    ParamSchema,
    RateLimit,
    RetryPolicy,
    ServiceEndpoint,
)
from flydek.knowledge.models import KnowledgeDocument

if TYPE_CHECKING:
    from flydek.catalog.repository import CatalogRepository
    from flydek.knowledge.indexer import KnowledgeIndexer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Systems
# ---------------------------------------------------------------------------

CUSTOMER_SERVICE = ExternalSystem(
    id="sys-customer-service",
    name="Customer Service",
    description=(
        "Core customer profile and account management system. Provides access "
        "to customer demographics, contact information, account status, and "
        "account lifecycle operations such as suspension and reactivation."
    ),
    base_url="https://api.internal.bank/customers/v2",
    auth_config=AuthConfig(
        auth_type=AuthType.OAUTH2,
        credential_id="cred-customer-svc",
        token_url="https://auth.internal.bank/oauth2/token",
        scopes=["customers:read", "customers:write"],
    ),
    health_check_path="/health",
    tags=["core", "customers", "accounts"],
    status=SystemStatus.ACTIVE,
    metadata={"owner": "retail-platform-team", "tier": "1"},
)

PRODUCT_CATALOG = ExternalSystem(
    id="sys-product-catalog",
    name="Product Catalog",
    description=(
        "Banking product catalog and eligibility engine. Lists available "
        "deposit accounts, credit products, and loan offerings. Supports "
        "eligibility pre-checks based on customer attributes."
    ),
    base_url="https://api.internal.bank/products/v1",
    auth_config=AuthConfig(
        auth_type=AuthType.API_KEY,
        credential_id="cred-product-catalog",
        auth_headers={"X-Api-Key": "{{credential}}"},
    ),
    health_check_path="/health",
    tags=["products", "eligibility"],
    status=SystemStatus.ACTIVE,
    metadata={"owner": "product-team", "tier": "2"},
)

TRANSACTION_LEDGER = ExternalSystem(
    id="sys-transaction-ledger",
    name="Transaction Ledger",
    description=(
        "Immutable transaction ledger providing read access to customer "
        "transactions, periodic statements, and the ability to initiate "
        "refund requests that go through a two-phase approval workflow."
    ),
    base_url="https://api.internal.bank/ledger/v3",
    auth_config=AuthConfig(
        auth_type=AuthType.OAUTH2,
        credential_id="cred-ledger",
        token_url="https://auth.internal.bank/oauth2/token",
        scopes=["transactions:read", "transactions:refund"],
    ),
    health_check_path="/health",
    tags=["transactions", "ledger", "statements"],
    status=SystemStatus.ACTIVE,
    metadata={"owner": "core-banking-team", "tier": "1"},
)

SUPPORT_TICKETS = ExternalSystem(
    id="sys-support-tickets",
    name="Support Tickets",
    description=(
        "Customer support ticket management system. Handles creation, "
        "tracking, assignment, and resolution of support tickets across "
        "all customer service channels."
    ),
    base_url="https://api.internal.bank/support/v1",
    auth_config=AuthConfig(
        auth_type=AuthType.BEARER,
        credential_id="cred-support-tickets",
    ),
    health_check_path="/health",
    tags=["support", "tickets"],
    status=SystemStatus.ACTIVE,
    metadata={"owner": "support-engineering", "tier": "2"},
)

NOTIFICATIONS = ExternalSystem(
    id="sys-notifications",
    name="Notifications",
    description=(
        "Omni-channel notification gateway supporting email, SMS, and push "
        "notifications. Used to send transactional alerts, marketing "
        "communications, and support follow-ups to customers."
    ),
    base_url="https://api.internal.bank/notifications/v1",
    auth_config=AuthConfig(
        auth_type=AuthType.API_KEY,
        credential_id="cred-notifications",
        auth_headers={"X-Api-Key": "{{credential}}"},
    ),
    health_check_path="/health",
    tags=["notifications", "email", "sms"],
    status=SystemStatus.ACTIVE,
    metadata={"owner": "messaging-team", "tier": "2"},
)

SYSTEMS: list[ExternalSystem] = [
    CUSTOMER_SERVICE,
    PRODUCT_CATALOG,
    TRANSACTION_LEDGER,
    SUPPORT_TICKETS,
    NOTIFICATIONS,
]

# ---------------------------------------------------------------------------
# Endpoints -- Customer Service (4)
# ---------------------------------------------------------------------------

EP_GET_CUSTOMER_PROFILE = ServiceEndpoint(
    id="ep-get-customer-profile",
    system_id="sys-customer-service",
    name="Get Customer Profile",
    description=(
        "Retrieve the full profile for a customer including demographics, "
        "contact information, account summary, and KYC status."
    ),
    method=HttpMethod.GET,
    path="/customers/{customer_id}",
    path_params={
        "customer_id": ParamSchema(
            type="string",
            description="Unique customer identifier (UUID).",
        ),
    },
    query_params={
        "include_accounts": ParamSchema(
            type="boolean",
            description="When true, embed linked account summaries.",
            required=False,
            default="false",
        ),
    },
    response_schema={
        "type": "object",
        "properties": {
            "customer_id": {"type": "string"},
            "first_name": {"type": "string"},
            "last_name": {"type": "string"},
            "email": {"type": "string"},
            "phone": {"type": "string"},
            "date_of_birth": {"type": "string", "format": "date"},
            "kyc_status": {"type": "string", "enum": ["verified", "pending", "failed"]},
            "accounts": {"type": "array", "items": {"type": "object"}},
        },
    },
    when_to_use=(
        "Use when you need to look up a customer's personal details, verify "
        "their identity, or review their account relationships. This is "
        "typically the first call when handling any customer inquiry."
    ),
    examples=[
        "Look up the profile for customer C-12345.",
        "What is the email address on file for customer C-99001?",
        "Show me customer Jane Doe's account information.",
    ],
    risk_level=RiskLevel.READ,
    required_permissions=["customers:read"],
    rate_limit=RateLimit(max_requests=100, window_seconds=60),
    timeout_seconds=10.0,
    retry_policy=RetryPolicy(max_retries=3, backoff_factor=0.5),
    tags=["customers", "profile", "read"],
)

EP_SEARCH_CUSTOMERS = ServiceEndpoint(
    id="ep-search-customers",
    system_id="sys-customer-service",
    name="Search Customers",
    description=(
        "Search for customers by name, email, phone number, or account "
        "number. Returns a paginated list of matching customer summaries."
    ),
    method=HttpMethod.GET,
    path="/customers",
    query_params={
        "q": ParamSchema(
            type="string",
            description="Free-text search query (name, email, phone, or account number).",
        ),
        "limit": ParamSchema(
            type="integer",
            description="Maximum number of results to return.",
            required=False,
            default="20",
        ),
        "offset": ParamSchema(
            type="integer",
            description="Pagination offset.",
            required=False,
            default="0",
        ),
    },
    response_schema={
        "type": "object",
        "properties": {
            "total": {"type": "integer"},
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "full_name": {"type": "string"},
                        "email": {"type": "string"},
                    },
                },
            },
        },
    },
    when_to_use=(
        "Use when the caller provides a name, email, phone, or account "
        "number and you need to find the matching customer record. Prefer "
        "this over Get Customer Profile when you do not yet have the "
        "customer ID."
    ),
    examples=[
        "Find the customer whose email is jdoe@example.com.",
        "Search for customers named 'Michael Chen'.",
        "Look up the customer with phone number 555-0142.",
    ],
    risk_level=RiskLevel.READ,
    required_permissions=["customers:read"],
    rate_limit=RateLimit(max_requests=50, window_seconds=60),
    timeout_seconds=15.0,
    retry_policy=RetryPolicy(max_retries=2, backoff_factor=1.0),
    tags=["customers", "search", "read"],
)

EP_UPDATE_CONTACT_INFO = ServiceEndpoint(
    id="ep-update-contact-info",
    system_id="sys-customer-service",
    name="Update Contact Information",
    description=(
        "Update a customer's contact information such as email address, "
        "phone number, or mailing address. Changes are audited and may "
        "trigger a re-verification workflow."
    ),
    method=HttpMethod.PATCH,
    path="/customers/{customer_id}/contact",
    path_params={
        "customer_id": ParamSchema(
            type="string",
            description="Unique customer identifier (UUID).",
        ),
    },
    request_body={
        "type": "object",
        "properties": {
            "email": {"type": "string", "format": "email"},
            "phone": {"type": "string"},
            "mailing_address": {
                "type": "object",
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                    "state": {"type": "string"},
                    "zip_code": {"type": "string"},
                    "country": {"type": "string"},
                },
            },
        },
        "minProperties": 1,
    },
    response_schema={
        "type": "object",
        "properties": {
            "customer_id": {"type": "string"},
            "updated_fields": {"type": "array", "items": {"type": "string"}},
            "verification_required": {"type": "boolean"},
        },
    },
    when_to_use=(
        "Use when a customer requests a change to their email, phone number, "
        "or mailing address. Always confirm the new details with the customer "
        "before submitting. Do not use for name changes -- those require a "
        "separate identity verification process."
    ),
    examples=[
        "Update customer C-12345's email to newemail@example.com.",
        "Change the phone number for customer C-99001 to 555-0199.",
        "Update the mailing address for customer C-45678.",
    ],
    risk_level=RiskLevel.LOW_WRITE,
    required_permissions=["customers:write"],
    rate_limit=RateLimit(max_requests=30, window_seconds=60),
    timeout_seconds=15.0,
    retry_policy=RetryPolicy(max_retries=2, backoff_factor=1.0),
    tags=["customers", "contact", "write"],
)

EP_SUSPEND_ACCOUNT = ServiceEndpoint(
    id="ep-suspend-account",
    system_id="sys-customer-service",
    name="Suspend Account",
    description=(
        "Suspend a customer account. Blocks all debit transactions and card "
        "usage. Requires a documented reason. Can only be reversed by a "
        "senior agent or compliance officer."
    ),
    method=HttpMethod.POST,
    path="/customers/{customer_id}/suspend",
    path_params={
        "customer_id": ParamSchema(
            type="string",
            description="Unique customer identifier (UUID).",
        ),
    },
    request_body={
        "type": "object",
        "required": ["reason", "reason_code"],
        "properties": {
            "reason": {
                "type": "string",
                "description": "Free-text explanation for the suspension.",
            },
            "reason_code": {
                "type": "string",
                "enum": ["fraud_suspected", "compliance_hold", "customer_request", "delinquency"],
                "description": "Standardized reason code.",
            },
            "notify_customer": {
                "type": "boolean",
                "description": "Whether to send a suspension notification.",
                "default": True,
            },
        },
    },
    response_schema={
        "type": "object",
        "properties": {
            "customer_id": {"type": "string"},
            "suspension_id": {"type": "string"},
            "status": {"type": "string"},
            "suspended_at": {"type": "string", "format": "date-time"},
        },
    },
    when_to_use=(
        "Use only when there is a clear and documented reason to suspend a "
        "customer account, such as confirmed fraud, a compliance hold, or "
        "an explicit customer request. Refer to the Account Suspension "
        "Runbook before executing. This action is irreversible by the agent."
    ),
    examples=[
        "Suspend customer C-12345's account due to suspected fraud.",
        "Place a compliance hold on account for customer C-99001.",
        "Customer C-45678 has requested their account be frozen.",
    ],
    risk_level=RiskLevel.HIGH_WRITE,
    required_permissions=["customers:write", "accounts:suspend"],
    rate_limit=RateLimit(max_requests=10, window_seconds=60),
    timeout_seconds=20.0,
    retry_policy=RetryPolicy(max_retries=1, backoff_factor=2.0),
    tags=["customers", "accounts", "suspension", "high-risk"],
)

# ---------------------------------------------------------------------------
# Endpoints -- Product Catalog (3)
# ---------------------------------------------------------------------------

EP_LIST_PRODUCTS = ServiceEndpoint(
    id="ep-list-products",
    system_id="sys-product-catalog",
    name="List Products",
    description=(
        "List all available banking products filtered by category. Returns "
        "product summaries including name, category, and key features."
    ),
    method=HttpMethod.GET,
    path="/products",
    query_params={
        "category": ParamSchema(
            type="string",
            description="Product category filter.",
            required=False,
            enum=["checking", "savings", "credit_card", "loan", "mortgage", "investment"],
        ),
        "active_only": ParamSchema(
            type="boolean",
            description="Return only currently offered products.",
            required=False,
            default="true",
        ),
    },
    response_schema={
        "type": "object",
        "properties": {
            "products": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string"},
                        "name": {"type": "string"},
                        "category": {"type": "string"},
                        "description": {"type": "string"},
                        "annual_fee": {"type": "number"},
                    },
                },
            },
        },
    },
    when_to_use=(
        "Use when a customer asks about available products, wants to compare "
        "options, or you need to identify which products are offered in a "
        "specific category."
    ),
    examples=[
        "What savings accounts does the bank offer?",
        "Show me all available credit card products.",
        "List the current mortgage options.",
    ],
    risk_level=RiskLevel.READ,
    required_permissions=["products:read"],
    rate_limit=RateLimit(max_requests=200, window_seconds=60),
    timeout_seconds=10.0,
    tags=["products", "catalog", "read"],
)

EP_GET_PRODUCT_DETAILS = ServiceEndpoint(
    id="ep-get-product-details",
    system_id="sys-product-catalog",
    name="Get Product Details",
    description=(
        "Retrieve detailed information about a specific banking product "
        "including terms, rates, fees, and eligibility criteria."
    ),
    method=HttpMethod.GET,
    path="/products/{product_id}",
    path_params={
        "product_id": ParamSchema(
            type="string",
            description="Unique product identifier.",
        ),
    },
    response_schema={
        "type": "object",
        "properties": {
            "product_id": {"type": "string"},
            "name": {"type": "string"},
            "category": {"type": "string"},
            "description": {"type": "string"},
            "interest_rate": {"type": "number"},
            "annual_fee": {"type": "number"},
            "minimum_balance": {"type": "number"},
            "terms_and_conditions_url": {"type": "string"},
            "eligibility_criteria": {
                "type": "object",
                "properties": {
                    "min_credit_score": {"type": "integer"},
                    "min_income": {"type": "number"},
                    "min_age": {"type": "integer"},
                },
            },
        },
    },
    when_to_use=(
        "Use when a customer asks for detailed information about a specific "
        "product, such as interest rates, fees, or terms and conditions."
    ),
    examples=[
        "What is the interest rate on the Premium Savings account?",
        "Tell me more about the Platinum credit card.",
        "What are the fees for product PRD-1001?",
    ],
    risk_level=RiskLevel.READ,
    required_permissions=["products:read"],
    rate_limit=RateLimit(max_requests=200, window_seconds=60),
    timeout_seconds=10.0,
    tags=["products", "details", "read"],
)

EP_CHECK_ELIGIBILITY = ServiceEndpoint(
    id="ep-check-eligibility",
    system_id="sys-product-catalog",
    name="Check Eligibility",
    description=(
        "Check whether a customer is eligible for a specific banking "
        "product based on their profile and financial information."
    ),
    method=HttpMethod.POST,
    path="/products/{product_id}/eligibility",
    path_params={
        "product_id": ParamSchema(
            type="string",
            description="Unique product identifier.",
        ),
    },
    request_body={
        "type": "object",
        "required": ["customer_id"],
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "Customer to evaluate eligibility for.",
            },
        },
    },
    response_schema={
        "type": "object",
        "properties": {
            "eligible": {"type": "boolean"},
            "reasons": {"type": "array", "items": {"type": "string"}},
            "alternative_products": {"type": "array", "items": {"type": "string"}},
        },
    },
    when_to_use=(
        "Use when a customer wants to know if they qualify for a specific "
        "product. Always retrieve the customer profile first to confirm "
        "their identity before running an eligibility check."
    ),
    examples=[
        "Is customer C-12345 eligible for the Platinum credit card?",
        "Can customer C-99001 qualify for the Home Equity loan?",
        "Check if customer C-45678 meets the criteria for Premium Savings.",
    ],
    risk_level=RiskLevel.READ,
    required_permissions=["products:read", "customers:read"],
    rate_limit=RateLimit(max_requests=50, window_seconds=60),
    timeout_seconds=20.0,
    retry_policy=RetryPolicy(max_retries=2, backoff_factor=1.0),
    tags=["products", "eligibility", "read"],
)

# ---------------------------------------------------------------------------
# Endpoints -- Transaction Ledger (3)
# ---------------------------------------------------------------------------

EP_GET_TRANSACTIONS = ServiceEndpoint(
    id="ep-get-transactions",
    system_id="sys-transaction-ledger",
    name="Get Transactions",
    description=(
        "Retrieve a paginated list of transactions for a customer account "
        "within a date range. Supports filtering by transaction type, "
        "amount range, and merchant."
    ),
    method=HttpMethod.GET,
    path="/accounts/{account_id}/transactions",
    path_params={
        "account_id": ParamSchema(
            type="string",
            description="Unique account identifier.",
        ),
    },
    query_params={
        "start_date": ParamSchema(
            type="string",
            description="Start date for the query range (ISO 8601).",
        ),
        "end_date": ParamSchema(
            type="string",
            description="End date for the query range (ISO 8601).",
        ),
        "type": ParamSchema(
            type="string",
            description="Transaction type filter.",
            required=False,
            enum=["debit", "credit", "transfer", "fee", "interest"],
        ),
        "limit": ParamSchema(
            type="integer",
            description="Maximum number of results.",
            required=False,
            default="50",
        ),
    },
    response_schema={
        "type": "object",
        "properties": {
            "account_id": {"type": "string"},
            "transactions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "transaction_id": {"type": "string"},
                        "date": {"type": "string", "format": "date-time"},
                        "type": {"type": "string"},
                        "amount": {"type": "number"},
                        "description": {"type": "string"},
                        "merchant": {"type": "string"},
                        "balance_after": {"type": "number"},
                    },
                },
            },
            "total": {"type": "integer"},
        },
    },
    when_to_use=(
        "Use when a customer asks about recent transactions, wants to "
        "verify a specific charge, or needs a transaction history for a "
        "given period."
    ),
    examples=[
        "Show me the last 10 transactions on account A-5001.",
        "What transactions did customer C-12345 make in January 2026?",
        "Are there any debit transactions over $500 on account A-5001?",
    ],
    risk_level=RiskLevel.READ,
    required_permissions=["transactions:read"],
    rate_limit=RateLimit(max_requests=60, window_seconds=60),
    timeout_seconds=15.0,
    retry_policy=RetryPolicy(max_retries=3, backoff_factor=0.5),
    tags=["transactions", "ledger", "read"],
)

EP_GET_STATEMENT = ServiceEndpoint(
    id="ep-get-statement",
    system_id="sys-transaction-ledger",
    name="Get Statement",
    description=(
        "Generate or retrieve a periodic account statement in PDF or JSON "
        "format. Statements are generated monthly and can be retrieved for "
        "any past period."
    ),
    method=HttpMethod.GET,
    path="/accounts/{account_id}/statements/{period}",
    path_params={
        "account_id": ParamSchema(
            type="string",
            description="Unique account identifier.",
        ),
        "period": ParamSchema(
            type="string",
            description="Statement period in YYYY-MM format.",
            pattern=r"^\d{4}-\d{2}$",
        ),
    },
    query_params={
        "format": ParamSchema(
            type="string",
            description="Output format.",
            required=False,
            default="json",
            enum=["json", "pdf"],
        ),
    },
    response_schema={
        "type": "object",
        "properties": {
            "account_id": {"type": "string"},
            "period": {"type": "string"},
            "opening_balance": {"type": "number"},
            "closing_balance": {"type": "number"},
            "total_credits": {"type": "number"},
            "total_debits": {"type": "number"},
            "transaction_count": {"type": "integer"},
        },
    },
    when_to_use=(
        "Use when a customer requests a monthly statement or needs a "
        "summary of account activity for a specific month. Prefer Get "
        "Transactions for ad-hoc date range queries."
    ),
    examples=[
        "Get the January 2026 statement for account A-5001.",
        "Can I see my December 2025 bank statement?",
        "Download the statement for account A-7002 for 2025-11.",
    ],
    risk_level=RiskLevel.READ,
    required_permissions=["transactions:read", "statements:read"],
    rate_limit=RateLimit(max_requests=30, window_seconds=60),
    timeout_seconds=20.0,
    tags=["transactions", "statements", "read"],
)

EP_INITIATE_REFUND = ServiceEndpoint(
    id="ep-initiate-refund",
    system_id="sys-transaction-ledger",
    name="Initiate Refund",
    description=(
        "Initiate a refund for a specific transaction. The refund enters a "
        "two-phase approval workflow: amounts up to $100 are auto-approved; "
        "larger amounts require supervisor approval."
    ),
    method=HttpMethod.POST,
    path="/transactions/{transaction_id}/refund",
    path_params={
        "transaction_id": ParamSchema(
            type="string",
            description="Unique transaction identifier to refund.",
        ),
    },
    request_body={
        "type": "object",
        "required": ["amount", "reason"],
        "properties": {
            "amount": {
                "type": "number",
                "description": "Refund amount (must not exceed the original transaction).",
            },
            "reason": {
                "type": "string",
                "description": "Explanation for the refund.",
            },
            "reason_code": {
                "type": "string",
                "enum": ["duplicate_charge", "merchant_error", "service_issue", "goodwill"],
                "description": "Standardized refund reason code.",
            },
        },
    },
    response_schema={
        "type": "object",
        "properties": {
            "refund_id": {"type": "string"},
            "transaction_id": {"type": "string"},
            "amount": {"type": "number"},
            "status": {"type": "string", "enum": ["approved", "pending_approval", "rejected"]},
            "estimated_completion": {"type": "string", "format": "date"},
        },
    },
    when_to_use=(
        "Use when a customer disputes a charge and a refund is warranted. "
        "Always verify the original transaction exists and confirm the "
        "refund amount with the customer first. Refer to the Refund Policy "
        "document for limits and rules."
    ),
    examples=[
        "Refund the $45.99 charge on transaction TXN-9001 -- duplicate charge.",
        "Customer C-12345 is disputing a $200 merchant error on TXN-8050.",
        "Issue a goodwill credit of $25 for transaction TXN-7700.",
    ],
    risk_level=RiskLevel.HIGH_WRITE,
    required_permissions=["transactions:refund"],
    rate_limit=RateLimit(max_requests=20, window_seconds=60),
    timeout_seconds=25.0,
    retry_policy=RetryPolicy(max_retries=1, backoff_factor=2.0),
    tags=["transactions", "refund", "high-risk"],
)

# ---------------------------------------------------------------------------
# Endpoints -- Support Tickets (3)
# ---------------------------------------------------------------------------

EP_LIST_TICKETS = ServiceEndpoint(
    id="ep-list-tickets",
    system_id="sys-support-tickets",
    name="List Tickets",
    description=(
        "List support tickets for a customer, optionally filtered by status "
        "or date range. Returns a paginated list of ticket summaries."
    ),
    method=HttpMethod.GET,
    path="/tickets",
    query_params={
        "customer_id": ParamSchema(
            type="string",
            description="Filter tickets by customer ID.",
        ),
        "status": ParamSchema(
            type="string",
            description="Filter by ticket status.",
            required=False,
            enum=["open", "in_progress", "resolved", "closed"],
        ),
        "limit": ParamSchema(
            type="integer",
            description="Maximum number of results.",
            required=False,
            default="20",
        ),
    },
    response_schema={
        "type": "object",
        "properties": {
            "total": {"type": "integer"},
            "tickets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ticket_id": {"type": "string"},
                        "subject": {"type": "string"},
                        "status": {"type": "string"},
                        "created_at": {"type": "string", "format": "date-time"},
                        "priority": {"type": "string"},
                    },
                },
            },
        },
    },
    when_to_use=(
        "Use when you need to check a customer's existing support tickets "
        "before creating a new one, or when a customer asks about the "
        "status of their open cases."
    ),
    examples=[
        "Show me all open tickets for customer C-12345.",
        "Does customer C-99001 have any existing support cases?",
        "List recent tickets for customer C-45678.",
    ],
    risk_level=RiskLevel.READ,
    required_permissions=["tickets:read"],
    rate_limit=RateLimit(max_requests=100, window_seconds=60),
    timeout_seconds=10.0,
    tags=["support", "tickets", "read"],
)

EP_CREATE_TICKET = ServiceEndpoint(
    id="ep-create-ticket",
    system_id="sys-support-tickets",
    name="Create Ticket",
    description=(
        "Create a new support ticket for a customer. Assigns a ticket ID "
        "and routes it to the appropriate support queue based on the "
        "category and priority."
    ),
    method=HttpMethod.POST,
    path="/tickets",
    request_body={
        "type": "object",
        "required": ["customer_id", "subject", "description", "category"],
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "Customer the ticket is for.",
            },
            "subject": {
                "type": "string",
                "description": "Brief summary of the issue.",
            },
            "description": {
                "type": "string",
                "description": "Detailed description of the customer's issue.",
            },
            "category": {
                "type": "string",
                "enum": [
                    "account_inquiry",
                    "transaction_dispute",
                    "technical_issue",
                    "product_question",
                    "complaint",
                    "other",
                ],
                "description": "Issue category for routing.",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Ticket priority.",
                "default": "medium",
            },
        },
    },
    response_schema={
        "type": "object",
        "properties": {
            "ticket_id": {"type": "string"},
            "status": {"type": "string"},
            "created_at": {"type": "string", "format": "date-time"},
            "assigned_queue": {"type": "string"},
        },
    },
    when_to_use=(
        "Use when a customer issue cannot be resolved immediately and needs "
        "to be tracked. Always check for existing open tickets first to "
        "avoid duplicates."
    ),
    examples=[
        "Create a ticket for customer C-12345 about a missing direct deposit.",
        "Open a high-priority case for customer C-99001 -- their card was stolen.",
        "File a complaint ticket for customer C-45678 regarding service at the branch.",
    ],
    risk_level=RiskLevel.LOW_WRITE,
    required_permissions=["tickets:write"],
    rate_limit=RateLimit(max_requests=30, window_seconds=60),
    timeout_seconds=15.0,
    retry_policy=RetryPolicy(max_retries=2, backoff_factor=1.0),
    tags=["support", "tickets", "write"],
)

EP_CLOSE_TICKET = ServiceEndpoint(
    id="ep-close-ticket",
    system_id="sys-support-tickets",
    name="Close Ticket",
    description=(
        "Close a resolved support ticket with a resolution summary. The "
        "customer will receive a satisfaction survey after closure."
    ),
    method=HttpMethod.POST,
    path="/tickets/{ticket_id}/close",
    path_params={
        "ticket_id": ParamSchema(
            type="string",
            description="Unique ticket identifier.",
        ),
    },
    request_body={
        "type": "object",
        "required": ["resolution_summary"],
        "properties": {
            "resolution_summary": {
                "type": "string",
                "description": "Summary of how the issue was resolved.",
            },
            "resolution_code": {
                "type": "string",
                "enum": [
                    "resolved",
                    "duplicate",
                    "no_action_needed",
                    "escalated",
                    "customer_withdrew",
                ],
                "description": "Standardized resolution code.",
            },
        },
    },
    response_schema={
        "type": "object",
        "properties": {
            "ticket_id": {"type": "string"},
            "status": {"type": "string"},
            "closed_at": {"type": "string", "format": "date-time"},
        },
    },
    when_to_use=(
        "Use when a support issue has been fully resolved and the customer "
        "has confirmed satisfaction, or when the ticket is a duplicate of "
        "an existing case."
    ),
    examples=[
        "Close ticket TKT-4001 -- issue was resolved by issuing a refund.",
        "Mark ticket TKT-4050 as duplicate of TKT-4001.",
        "Close ticket TKT-4100 -- customer no longer needs assistance.",
    ],
    risk_level=RiskLevel.LOW_WRITE,
    required_permissions=["tickets:write"],
    rate_limit=RateLimit(max_requests=30, window_seconds=60),
    timeout_seconds=10.0,
    tags=["support", "tickets", "write"],
)

# ---------------------------------------------------------------------------
# Endpoints -- Notifications (2)
# ---------------------------------------------------------------------------

EP_SEND_EMAIL = ServiceEndpoint(
    id="ep-send-email",
    system_id="sys-notifications",
    name="Send Email",
    description=(
        "Send a transactional email to a customer using a pre-approved "
        "template. Supports variable substitution for personalisation."
    ),
    method=HttpMethod.POST,
    path="/email/send",
    request_body={
        "type": "object",
        "required": ["customer_id", "template_id"],
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "Recipient customer ID.",
            },
            "template_id": {
                "type": "string",
                "description": "Pre-approved email template identifier.",
                "enum": [
                    "welcome",
                    "ticket_created",
                    "ticket_resolved",
                    "refund_processed",
                    "account_suspended",
                    "general_notification",
                ],
            },
            "variables": {
                "type": "object",
                "description": "Key-value pairs for template variable substitution.",
            },
        },
    },
    response_schema={
        "type": "object",
        "properties": {
            "message_id": {"type": "string"},
            "status": {"type": "string", "enum": ["queued", "sent", "failed"]},
        },
    },
    when_to_use=(
        "Use to send a follow-up or confirmation email to a customer. Only "
        "pre-approved templates are available -- free-form emails are not "
        "supported. Select the template that best matches the context."
    ),
    examples=[
        "Send a ticket-created confirmation email to customer C-12345.",
        "Email customer C-99001 that their refund has been processed.",
        "Send a general notification to customer C-45678 about their inquiry.",
    ],
    risk_level=RiskLevel.LOW_WRITE,
    required_permissions=["notifications:send"],
    rate_limit=RateLimit(max_requests=50, window_seconds=60),
    timeout_seconds=10.0,
    retry_policy=RetryPolicy(max_retries=3, backoff_factor=1.0),
    tags=["notifications", "email", "write"],
)

EP_SEND_SMS = ServiceEndpoint(
    id="ep-send-sms",
    system_id="sys-notifications",
    name="Send SMS",
    description=(
        "Send an SMS message to a customer's registered phone number using "
        "a pre-approved template. Messages are limited to 160 characters "
        "after variable substitution."
    ),
    method=HttpMethod.POST,
    path="/sms/send",
    request_body={
        "type": "object",
        "required": ["customer_id", "template_id"],
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "Recipient customer ID.",
            },
            "template_id": {
                "type": "string",
                "description": "Pre-approved SMS template identifier.",
                "enum": [
                    "otp_verification",
                    "transaction_alert",
                    "appointment_reminder",
                    "general_alert",
                ],
            },
            "variables": {
                "type": "object",
                "description": "Key-value pairs for template variable substitution.",
            },
        },
    },
    response_schema={
        "type": "object",
        "properties": {
            "message_id": {"type": "string"},
            "status": {"type": "string", "enum": ["queued", "sent", "failed"]},
        },
    },
    when_to_use=(
        "Use to send an SMS alert or verification code to a customer. "
        "Prefer email for longer communications. Only use pre-approved "
        "templates."
    ),
    examples=[
        "Send a transaction alert SMS to customer C-12345.",
        "Text customer C-99001 an OTP verification code.",
        "Send an appointment reminder SMS to customer C-45678.",
    ],
    risk_level=RiskLevel.LOW_WRITE,
    required_permissions=["notifications:send"],
    rate_limit=RateLimit(max_requests=30, window_seconds=60),
    timeout_seconds=10.0,
    retry_policy=RetryPolicy(max_retries=3, backoff_factor=1.0),
    tags=["notifications", "sms", "write"],
)

EP_GET_NOTIFICATION_HISTORY = ServiceEndpoint(
    id="ep-get-notification-history",
    system_id="sys-notifications",
    name="Get Notification History",
    description=(
        "Retrieve the history of notifications sent to a customer across "
        "all channels (email, SMS, push). Useful for auditing and "
        "troubleshooting delivery issues."
    ),
    method=HttpMethod.GET,
    path="/notifications/history",
    query_params={
        "customer_id": ParamSchema(
            type="string",
            description="Customer ID to retrieve history for.",
        ),
        "channel": ParamSchema(
            type="string",
            description="Filter by notification channel.",
            required=False,
            enum=["email", "sms", "push"],
        ),
        "limit": ParamSchema(
            type="integer",
            description="Maximum number of results.",
            required=False,
            default="20",
        ),
    },
    response_schema={
        "type": "object",
        "properties": {
            "total": {"type": "integer"},
            "notifications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "message_id": {"type": "string"},
                        "channel": {"type": "string"},
                        "template_id": {"type": "string"},
                        "status": {"type": "string"},
                        "sent_at": {"type": "string", "format": "date-time"},
                    },
                },
            },
        },
    },
    when_to_use=(
        "Use when a customer says they did not receive a notification, or "
        "when you need to verify that a previous communication was delivered "
        "successfully."
    ),
    examples=[
        "Show all emails sent to customer C-12345 in the last week.",
        "Did customer C-99001 receive the refund confirmation SMS?",
        "What notifications were sent to customer C-45678 recently?",
    ],
    risk_level=RiskLevel.READ,
    required_permissions=["notifications:read"],
    rate_limit=RateLimit(max_requests=100, window_seconds=60),
    timeout_seconds=10.0,
    tags=["notifications", "history", "read"],
)

ENDPOINTS: list[ServiceEndpoint] = [
    # Customer Service
    EP_GET_CUSTOMER_PROFILE,
    EP_SEARCH_CUSTOMERS,
    EP_UPDATE_CONTACT_INFO,
    EP_SUSPEND_ACCOUNT,
    # Product Catalog
    EP_LIST_PRODUCTS,
    EP_GET_PRODUCT_DETAILS,
    EP_CHECK_ELIGIBILITY,
    # Transaction Ledger
    EP_GET_TRANSACTIONS,
    EP_GET_STATEMENT,
    EP_INITIATE_REFUND,
    # Support Tickets
    EP_LIST_TICKETS,
    EP_CREATE_TICKET,
    EP_CLOSE_TICKET,
    # Notifications
    EP_SEND_EMAIL,
    EP_SEND_SMS,
    EP_GET_NOTIFICATION_HISTORY,
]

# ---------------------------------------------------------------------------
# Knowledge Documents
# ---------------------------------------------------------------------------

DOC_CUSTOMER_ONBOARDING = KnowledgeDocument(
    id="doc-customer-onboarding",
    title="Customer Onboarding Procedure",
    content=(
        "Customer Onboarding Procedure\n"
        "=============================\n\n"
        "Purpose: This procedure defines the steps for onboarding a new retail "
        "banking customer, from initial application to account activation.\n\n"
        "1. Identity Verification\n"
        "   - Collect government-issued photo ID (passport, driver's license, "
        "or national ID card).\n"
        "   - Verify the document against the issuing authority's database.\n"
        "   - Capture a live selfie for biometric matching.\n"
        "   - If biometric match confidence is below 85%, escalate to a human "
        "reviewer in the compliance team.\n\n"
        "2. KYC and AML Screening\n"
        "   - Run the customer's name, date of birth, and address through the "
        "sanctions screening service.\n"
        "   - Check the PEP (Politically Exposed Persons) database.\n"
        "   - If any flags are raised, place the application on hold and "
        "notify the compliance officer.\n"
        "   - Record all screening results in the audit log.\n\n"
        "3. Account Selection\n"
        "   - Present the customer with eligible account types based on their "
        "profile (see Product Catalog).\n"
        "   - Walk through key terms: minimum balance, fees, interest rates, "
        "and overdraft options.\n"
        "   - Obtain the customer's informed consent and digital signature.\n\n"
        "4. Initial Funding\n"
        "   - Accept the initial deposit via bank transfer, debit card, or "
        "certified check.\n"
        "   - Minimum opening deposit varies by product (refer to Product "
        "Catalog for amounts).\n"
        "   - Issue a temporary virtual card number for immediate use.\n\n"
        "5. Welcome Package\n"
        "   - Trigger the welcome email template with account details.\n"
        "   - Mail the physical debit card within 5 business days.\n"
        "   - Schedule a 30-day check-in call or chatbot follow-up.\n"
        "   - Create a low-priority onboarding ticket in the support system "
        "for tracking purposes.\n\n"
        "Exceptions:\n"
        "- Customers under 18 require a joint account with a legal guardian.\n"
        "- Non-resident applications follow the enhanced due diligence (EDD) "
        "path and require additional documentation.\n"
        "- Business accounts follow a separate onboarding flow managed by "
        "the commercial banking team."
    ),
    source="internal-wiki://procedures/customer-onboarding",
    tags=["procedure", "onboarding", "kyc", "compliance"],
    metadata={"document_type": "PROCEDURE", "version": "3.1", "last_reviewed": "2026-01-15"},
)

DOC_REFUND_POLICY = KnowledgeDocument(
    id="doc-refund-policy",
    title="Refund Policy",
    content=(
        "Refund Policy\n"
        "=============\n\n"
        "Scope: This policy governs all customer-facing refund requests "
        "processed through the Transaction Ledger system.\n\n"
        "1. Eligibility Criteria\n"
        "   - Refunds may be issued for duplicate charges, merchant errors, "
        "unauthorized transactions, and service-related goodwill credits.\n"
        "   - The original transaction must be within the past 90 days.\n"
        "   - Refunds for transactions older than 90 days require director-level "
        "approval.\n\n"
        "2. Refund Limits\n"
        "   - Auto-approved: Refunds up to $100.00 with a valid reason code "
        "are automatically approved and credited within 1 business day.\n"
        "   - Supervisor approval: Refunds between $100.01 and $1,000.00 "
        "require supervisor sign-off within 24 hours.\n"
        "   - Director approval: Refunds exceeding $1,000.00 require director "
        "approval and must include supporting documentation.\n"
        "   - Daily agent limit: No single agent may issue more than $2,500 "
        "in total refunds per day.\n\n"
        "3. Reason Codes\n"
        "   - DUPLICATE_CHARGE: The same transaction was charged more than "
        "once. Requires transaction IDs of both charges.\n"
        "   - MERCHANT_ERROR: The merchant charged an incorrect amount. "
        "Requires the expected vs. actual amount.\n"
        "   - SERVICE_ISSUE: The bank's service caused the customer "
        "inconvenience. Requires a brief explanation.\n"
        "   - GOODWILL: A discretionary credit to maintain customer "
        "satisfaction. Limited to $50.00 per incident.\n\n"
        "4. Processing Timeline\n"
        "   - Auto-approved refunds: credited within 1 business day.\n"
        "   - Supervisor-approved refunds: 1-3 business days.\n"
        "   - Director-approved refunds: 3-5 business days.\n"
        "   - The customer must be informed of the estimated timeline.\n\n"
        "5. Audit and Compliance\n"
        "   - Every refund is logged in the immutable audit trail.\n"
        "   - Refund patterns are reviewed monthly by the fraud analytics "
        "team.\n"
        "   - Agents with abnormal refund volumes are flagged for review."
    ),
    source="internal-wiki://policies/refund-policy",
    tags=["policy", "refunds", "transactions", "compliance"],
    metadata={"document_type": "POLICY", "version": "2.4", "last_reviewed": "2026-02-01"},
)

DOC_ACCOUNT_SUSPENSION_RUNBOOK = KnowledgeDocument(
    id="doc-account-suspension",
    title="Account Suspension Runbook",
    content=(
        "Account Suspension Runbook\n"
        "==========================\n\n"
        "Purpose: This runbook provides step-by-step instructions for "
        "suspending a customer account and the criteria that must be met "
        "before taking this action.\n\n"
        "1. When to Suspend\n"
        "   - Confirmed or strongly suspected fraudulent activity.\n"
        "   - Court order or regulatory directive.\n"
        "   - Customer request (e.g., lost card, travel freeze).\n"
        "   - Severe delinquency (more than 90 days past due).\n"
        "   - Do NOT suspend for minor disputes, late payments under 60 days, "
        "or as a punitive measure.\n\n"
        "2. Pre-Suspension Checklist\n"
        "   - Verify the customer identity using at least two factors.\n"
        "   - Document the reason and obtain the appropriate reason code.\n"
        "   - For fraud cases, check if a fraud investigation case already "
        "exists. If not, create one.\n"
        "   - For compliance holds, confirm you have a reference number from "
        "the compliance team.\n"
        "   - Notify the customer verbally (if on a call) before executing.\n\n"
        "3. Executing the Suspension\n"
        "   - Call the Suspend Account endpoint with the customer ID, reason, "
        "and reason code.\n"
        "   - Set notify_customer to true unless the compliance team "
        "explicitly instructs otherwise.\n"
        "   - Record the suspension_id returned by the API.\n"
        "   - Create or update the support ticket with the suspension details.\n\n"
        "4. Post-Suspension Actions\n"
        "   - Send the account_suspended email notification.\n"
        "   - If the customer has pending direct deposits, alert the "
        "operations team.\n"
        "   - Schedule a review in 30 days if the suspension is precautionary.\n"
        "   - For customer-requested freezes, confirm the expected duration "
        "and set a reminder.\n\n"
        "5. Reactivation\n"
        "   - Only a senior agent or compliance officer can reactivate a "
        "suspended account.\n"
        "   - The reactivation request must include the original suspension "
        "ID and supporting evidence that the issue is resolved.\n"
        "   - A fresh KYC check may be required if the account was suspended "
        "for more than 90 days."
    ),
    source="internal-wiki://runbooks/account-suspension",
    tags=["runbook", "suspension", "accounts", "fraud", "compliance"],
    metadata={"document_type": "RUNBOOK", "version": "1.8", "last_reviewed": "2026-01-20"},
)

DOC_PRODUCT_FAQ = KnowledgeDocument(
    id="doc-product-faq",
    title="Product FAQ",
    content=(
        "Product Frequently Asked Questions\n"
        "===================================\n\n"
        "Q: What types of checking accounts do you offer?\n"
        "A: We offer three checking account tiers: Basic Checking (no minimum "
        "balance, $5/month fee), Standard Checking (minimum $1,000 balance, "
        "no monthly fee), and Premium Checking (minimum $10,000 balance, "
        "no fees, includes premium perks like airport lounge access).\n\n"
        "Q: How do I earn interest on my savings account?\n"
        "A: All savings accounts earn interest calculated daily and credited "
        "monthly. The current rate is 4.25% APY for balances over $5,000 and "
        "3.50% APY for balances under $5,000. Rates are variable and may "
        "change with Federal Reserve policy updates.\n\n"
        "Q: What credit cards are available?\n"
        "A: We offer the Everyday Rewards Card (no annual fee, 1.5% cash "
        "back), the Travel Platinum Card ($95/year, 3x points on travel and "
        "dining), and the Business Advantage Card ($150/year, 2% cash back on "
        "all business purchases). All cards require a credit score of 680 or "
        "higher.\n\n"
        "Q: Can I apply for a personal loan online?\n"
        "A: Yes. Personal loans from $2,000 to $50,000 can be applied for "
        "through online banking or by speaking with an agent. Approval "
        "typically takes 1-2 business days. Rates range from 6.99% to 18.99% "
        "APR based on creditworthiness.\n\n"
        "Q: What mortgage products do you offer?\n"
        "A: We offer 15-year and 30-year fixed-rate mortgages, 5/1 and 7/1 "
        "adjustable-rate mortgages (ARM), and Home Equity Lines of Credit "
        "(HELOC). Pre-qualification is available online and does not affect "
        "your credit score.\n\n"
        "Q: How do I upgrade my account?\n"
        "A: Contact customer support or visit a branch. Upgrades are subject "
        "to eligibility checks. There is no fee for upgrading, but the new "
        "account's minimum balance requirements take effect immediately.\n\n"
        "Q: Is there a fee for closing an account?\n"
        "A: Accounts open for more than 6 months can be closed at no charge. "
        "Accounts closed within the first 6 months incur a $25 early closure "
        "fee. Outstanding balances must be paid before closure."
    ),
    source="internal-wiki://faq/products",
    tags=["faq", "products", "accounts", "credit-cards", "loans"],
    metadata={"document_type": "FAQ", "version": "5.2", "last_reviewed": "2026-02-10"},
)

DOC_COMPLIANCE_GUIDELINES = KnowledgeDocument(
    id="doc-compliance-guidelines",
    title="Compliance Guidelines",
    content=(
        "Compliance and Data Handling Guidelines\n"
        "=======================================\n\n"
        "Purpose: These guidelines define mandatory data handling, privacy, "
        "and regulatory compliance requirements for all customer service "
        "agents and automated systems.\n\n"
        "1. Personally Identifiable Information (PII)\n"
        "   - PII includes: full name, date of birth, Social Security Number "
        "(SSN), account numbers, email, phone, and physical address.\n"
        "   - Never display full SSN; use the last four digits only.\n"
        "   - Mask account numbers in logs and chat transcripts (show only "
        "the last four digits).\n"
        "   - Do not store PII in temporary files, local caches, or chat "
        "history beyond the session.\n\n"
        "2. Customer Authentication\n"
        "   - All account-modifying operations require the customer to be "
        "authenticated via at least two of the following: knowledge-based "
        "question, SMS OTP, email OTP, or biometric verification.\n"
        "   - Read-only lookups require single-factor authentication.\n"
        "   - Document the authentication method used in the interaction "
        "log.\n\n"
        "3. Data Retention\n"
        "   - Customer interaction records are retained for 7 years per "
        "regulatory requirements.\n"
        "   - Transaction records are immutable and retained indefinitely.\n"
        "   - Support ticket content is retained for 5 years after closure.\n"
        "   - Notification logs are retained for 3 years.\n\n"
        "4. Regulatory Requirements\n"
        "   - All operations must comply with the Gramm-Leach-Bliley Act "
        "(GLBA) for financial privacy.\n"
        "   - Customer communications must adhere to CAN-SPAM (email) and "
        "TCPA (SMS/phone) regulations.\n"
        "   - Cross-border data transfers must follow applicable data "
        "sovereignty laws.\n"
        "   - Suspicious activity must be reported per BSA/AML requirements.\n\n"
        "5. Incident Reporting\n"
        "   - Any suspected data breach must be reported to the Information "
        "Security team within 1 hour.\n"
        "   - Customer complaints about data misuse must be escalated to the "
        "Privacy Officer.\n"
        "   - All compliance incidents are tracked in the GRC (Governance, "
        "Risk, and Compliance) system.\n\n"
        "6. Agent Responsibilities\n"
        "   - Complete annual compliance training before handling customer "
        "data.\n"
        "   - Follow the principle of least privilege -- access only the data "
        "needed for the current task.\n"
        "   - Log out of all systems at the end of each shift.\n"
        "   - Report any unusual system behavior to the security operations "
        "center (SOC)."
    ),
    source="internal-wiki://policies/compliance-guidelines",
    tags=["policy", "compliance", "pii", "data-handling", "regulatory"],
    metadata={"document_type": "POLICY", "version": "4.0", "last_reviewed": "2026-02-05"},
)

KNOWLEDGE_DOCUMENTS: list[KnowledgeDocument] = [
    DOC_CUSTOMER_ONBOARDING,
    DOC_REFUND_POLICY,
    DOC_ACCOUNT_SUSPENSION_RUNBOOK,
    DOC_PRODUCT_FAQ,
    DOC_COMPLIANCE_GUIDELINES,
]

# ---------------------------------------------------------------------------
# Seed function
# ---------------------------------------------------------------------------


async def seed_banking_catalog(
    catalog_repo: CatalogRepository,
    knowledge_indexer: KnowledgeIndexer | None = None,
) -> None:
    """Seed the banking platform example domain.

    Creates five banking systems, sixteen service endpoints, and optionally
    indexes five knowledge-base documents.

    Parameters
    ----------
    catalog_repo:
        Repository used to persist systems and endpoints.
    knowledge_indexer:
        If provided, knowledge documents are indexed (chunked and embedded).
        When ``None`` the documents are skipped silently.
    """
    # 1. Systems
    for system in SYSTEMS:
        await catalog_repo.create_system(system)
        logger.info("Seeded system: %s", system.name)

    # 2. Endpoints
    for endpoint in ENDPOINTS:
        await catalog_repo.create_endpoint(endpoint)
        logger.info("Seeded endpoint: %s", endpoint.name)

    # 3. Knowledge documents (optional)
    if knowledge_indexer is not None:
        for document in KNOWLEDGE_DOCUMENTS:
            await knowledge_indexer.index_document(document)
            logger.info("Indexed knowledge document: %s", document.title)

    logger.info(
        "Banking seed complete: %d systems, %d endpoints, %d documents",
        len(SYSTEMS),
        len(ENDPOINTS),
        len(KNOWLEDGE_DOCUMENTS) if knowledge_indexer is not None else 0,
    )
