# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Google Drive adapter using Google Drive API v3."""

from __future__ import annotations

import io
import json
import logging
from pathlib import PurePosixPath

from flydesk.knowledge.document_source import (
    IMPORTABLE_EXTENSIONS,
    DocumentSourceFactory,
    DriveInfo,
    DriveItem,
)

logger = logging.getLogger(__name__)

# Google Workspace MIME types that can be exported.
_GOOGLE_EXPORT_MAP: dict[str, tuple[str, str]] = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/pdf",
        ".pdf",
    ),
}


class GoogleDriveAdapter:
    """Adapter for Google Drive API v3."""

    def __init__(self, config: dict) -> None:
        self._folder_id = config.get("folder_id", "")
        self._service_account_json = config.get("service_account_json", "")
        self._service = None

    def _get_service(self):
        if self._service is None:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            if self._service_account_json:
                info = json.loads(self._service_account_json)
                credentials = service_account.Credentials.from_service_account_info(
                    info,
                    scopes=["https://www.googleapis.com/auth/drive.readonly"],
                )
            else:
                from google.auth import default

                credentials, _ = default(
                    scopes=["https://www.googleapis.com/auth/drive.readonly"]
                )
            self._service = build("drive", "v3", credentials=credentials)
        return self._service

    @staticmethod
    def _is_importable(name: str) -> bool:
        return PurePosixPath(name).suffix.lower() in IMPORTABLE_EXTENSIONS

    @staticmethod
    def _is_google_doc(mime_type: str) -> bool:
        return mime_type in _GOOGLE_EXPORT_MAP

    async def validate_credentials(self) -> bool:
        try:
            service = self._get_service()
            service.about().get(fields="user").execute()
            return True
        except Exception:
            return False

    async def list_drives(self) -> list[DriveInfo]:
        drives: list[DriveInfo] = []
        try:
            service = self._get_service()
            # Add "My Drive" as the default personal drive.
            drives.append(
                DriveInfo(id="root", name="My Drive", type="personal")
            )
            # List shared drives.
            page_token = None
            while True:
                response = (
                    service.drives()
                    .list(pageSize=100, pageToken=page_token)
                    .execute()
                )
                for d in response.get("drives", []):
                    drives.append(
                        DriveInfo(
                            id=d["id"],
                            name=d.get("name", ""),
                            type="shared",
                        )
                    )
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        except Exception:
            logger.exception("Failed to list Google drives")
        return drives

    async def list_items(
        self, drive_id: str, folder_id: str = ""
    ) -> list[DriveItem]:
        service = self._get_service()
        parent = folder_id or self._folder_id or "root"
        query = f"'{parent}' in parents and trashed = false"

        items: list[DriveItem] = []
        page_token = None
        try:
            while True:
                kwargs: dict = {
                    "q": query,
                    "fields": "nextPageToken, files(id, name, mimeType, size, modifiedTime, parents)",
                    "pageSize": 100,
                    "pageToken": page_token,
                }
                if drive_id and drive_id != "root":
                    kwargs["driveId"] = drive_id
                    kwargs["includeItemsFromAllDrives"] = True
                    kwargs["supportsAllDrives"] = True
                    kwargs["corpora"] = "drive"

                response = service.files().list(**kwargs).execute()
                for f in response.get("files", []):
                    mime = f.get("mimeType", "")
                    is_folder = mime == "application/vnd.google-apps.folder"
                    name = f.get("name", "")

                    # For Google Docs, check if the export format is importable.
                    if self._is_google_doc(mime):
                        _, ext = _GOOGLE_EXPORT_MAP[mime]
                        if ext.lower() not in IMPORTABLE_EXTENSIONS:
                            continue
                    elif not is_folder and not self._is_importable(name):
                        continue

                    items.append(
                        DriveItem(
                            id=f["id"],
                            name=name,
                            path="",
                            is_folder=is_folder,
                            size=int(f.get("size", 0)),
                            modified_at=f.get("modifiedTime", ""),
                            mime_type=mime,
                        )
                    )
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        except Exception:
            logger.exception("Failed to list Google Drive items")
        return items

    async def get_file_content(self, drive_id: str, item_id: str) -> bytes:
        service = self._get_service()

        # Check if this is a Google Workspace file that needs export.
        meta = (
            service.files()
            .get(fileId=item_id, fields="mimeType", supportsAllDrives=True)
            .execute()
        )
        mime = meta.get("mimeType", "")

        if self._is_google_doc(mime):
            export_mime, _ = _GOOGLE_EXPORT_MAP[mime]
            request = service.files().export_media(
                fileId=item_id, mimeType=export_mime
            )
        else:
            request = service.files().get_media(
                fileId=item_id, supportsAllDrives=True
            )

        from googleapiclient.http import MediaIoBaseDownload

        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()

    async def aclose(self) -> None:
        self._service = None


DocumentSourceFactory.register("google_drive", GoogleDriveAdapter)
