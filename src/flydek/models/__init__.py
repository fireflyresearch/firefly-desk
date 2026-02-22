# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""SQLAlchemy ORM models for Firefly Desk."""

from flydek.models.audit import AuditEventRow
from flydek.models.base import Base
from flydek.models.catalog import CredentialRow, ExternalSystemRow, ServiceEndpointRow
from flydek.models.conversation import ConversationRow, MessageRow
from flydek.models.file_upload import FileUploadRow
from flydek.models.knowledge import EntityRow, RelationRow
from flydek.models.knowledge_base import DocumentChunkRow, KnowledgeDocumentRow
from flydek.models.llm import LLMProviderRow
from flydek.models.user_settings import AppSettingRow, UserSettingRow

__all__ = [
    "AppSettingRow",
    "AuditEventRow",
    "Base",
    "ConversationRow",
    "CredentialRow",
    "DocumentChunkRow",
    "EntityRow",
    "ExternalSystemRow",
    "FileUploadRow",
    "KnowledgeDocumentRow",
    "LLMProviderRow",
    "MessageRow",
    "RelationRow",
    "ServiceEndpointRow",
    "UserSettingRow",
]
