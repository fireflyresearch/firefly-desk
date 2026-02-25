# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""SSO Identity model -- links OIDC provider identities to local users."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flydesk.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SSOIdentityRow(Base):
    """ORM row for the ``sso_identities`` table."""

    __tablename__ = "sso_identities"
    __table_args__ = (
        UniqueConstraint("provider_id", "subject", name="uq_sso_identity_provider_subject"),
    )

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    provider_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("oidc_providers.id"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(512), nullable=False)  # OIDC 'sub' claim
    email: Mapped[str | None] = mapped_column(String(512), nullable=True)
    local_user_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("local_users.id"), nullable=False
    )
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # Relationships (viewonly — managed via explicit queries, not cascading writes)
    provider = relationship("OIDCProviderRow", lazy="selectin", viewonly=True)
    local_user = relationship("LocalUserRow", lazy="selectin", viewonly=True)
