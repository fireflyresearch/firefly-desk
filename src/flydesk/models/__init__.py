# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""SQLAlchemy ORM models for Firefly Desk."""

from flydesk.models.audit import AuditEventRow
from flydesk.models.base import Base
from flydesk.models.catalog import CredentialRow, ExternalSystemRow, ServiceEndpointRow
from flydesk.models.custom_tool import CustomToolRow
from flydesk.models.conversation import ConversationRow, MessageRow
from flydesk.models.export import ExportRow, ExportTemplateRow
from flydesk.models.file_upload import FileUploadRow
from flydesk.models.git_provider import GitProviderRow
from flydesk.models.job import JobRow
from flydesk.models.knowledge import EntityRow, RelationRow
from flydesk.models.knowledge_base import DocumentChunkRow, KnowledgeDocumentRow
from flydesk.models.local_user import LocalUserRow
from flydesk.models.process import BusinessProcessRow, ProcessDependencyRow, ProcessStepRow
from flydesk.models.llm import LLMProviderRow
from flydesk.models.oidc import OIDCProviderRow
from flydesk.models.role import RoleRow
from flydesk.models.sso_identity import SSOIdentityRow
from flydesk.models.user_role import UserRoleRow
from flydesk.models.user_settings import AppSettingRow, UserSettingRow

__all__ = [
    "AppSettingRow",
    "AuditEventRow",
    "Base",
    "BusinessProcessRow",
    "ConversationRow",
    "CredentialRow",
    "CustomToolRow",
    "DocumentChunkRow",
    "EntityRow",
    "ExportRow",
    "ExportTemplateRow",
    "ExternalSystemRow",
    "FileUploadRow",
    "GitProviderRow",
    "JobRow",
    "KnowledgeDocumentRow",
    "LLMProviderRow",
    "LocalUserRow",
    "MessageRow",
    "OIDCProviderRow",
    "ProcessDependencyRow",
    "ProcessStepRow",
    "RelationRow",
    "RoleRow",
    "ServiceEndpointRow",
    "SSOIdentityRow",
    "UserRoleRow",
    "UserSettingRow",
]
