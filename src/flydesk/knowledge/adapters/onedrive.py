# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""OneDrive adapter via Microsoft Graph API."""

from __future__ import annotations

import logging
from pathlib import PurePosixPath

from flydesk.knowledge.document_source import (
    IMPORTABLE_EXTENSIONS,
    DocumentSourceFactory,
    DriveInfo,
    DriveItem,
)

logger = logging.getLogger(__name__)

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class OneDriveAdapter:
    """Adapter for OneDrive via Microsoft Graph API."""

    def __init__(self, config: dict) -> None:
        self._tenant_id = config.get("tenant_id", "")
        self._client_id = config.get("client_id", "")
        self._client_secret = config.get("client_secret", "")
        self._drive_id = config.get("drive_id", "")
        self._folder_path = config.get("folder_path", "")
        self._msal_app = None
        self._access_token: str | None = None
        self._http_client = None

    def _get_msal_app(self):
        if self._msal_app is None:
            import msal

            self._msal_app = msal.ConfidentialClientApplication(
                client_id=self._client_id,
                client_credential=self._client_secret,
                authority=f"https://login.microsoftonline.com/{self._tenant_id}",
            )
        return self._msal_app

    def _acquire_token(self) -> str:
        app = self._get_msal_app()
        result = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            raise RuntimeError(
                f"Failed to acquire token: {result.get('error_description', 'unknown error')}"
            )
        return result["access_token"]

    async def _get_http_client(self):
        if self._http_client is None:
            import httpx

            self._access_token = self._acquire_token()
            self._http_client = httpx.AsyncClient(
                base_url=_GRAPH_BASE,
                headers={"Authorization": f"Bearer {self._access_token}"},
                timeout=30.0,
            )
        return self._http_client

    @staticmethod
    def _is_importable(name: str) -> bool:
        return PurePosixPath(name).suffix.lower() in IMPORTABLE_EXTENSIONS

    async def validate_credentials(self) -> bool:
        try:
            client = await self._get_http_client()
            response = await client.get("/me/drives")
            return response.status_code == 200
        except Exception:
            return False

    async def list_drives(self) -> list[DriveInfo]:
        try:
            client = await self._get_http_client()
            response = await client.get("/me/drives")
            response.raise_for_status()
            data = response.json()
            return [
                DriveInfo(
                    id=d["id"],
                    name=d.get("name", ""),
                    type=d.get("driveType", "personal"),
                )
                for d in data.get("value", [])
            ]
        except Exception:
            logger.exception("Failed to list OneDrive drives")
            return []

    async def list_items(
        self, drive_id: str, folder_id: str = ""
    ) -> list[DriveItem]:
        client = await self._get_http_client()
        if folder_id:
            url = f"/drives/{drive_id}/items/{folder_id}/children"
        else:
            url = f"/drives/{drive_id}/root/children"

        items: list[DriveItem] = []
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            for item in data.get("value", []):
                is_folder = "folder" in item
                name = item.get("name", "")
                if not is_folder and not self._is_importable(name):
                    continue
                items.append(
                    DriveItem(
                        id=item["id"],
                        name=name,
                        path=item.get("parentReference", {}).get("path", ""),
                        is_folder=is_folder,
                        size=item.get("size", 0),
                        modified_at=item.get("lastModifiedDateTime", ""),
                        mime_type=item.get("file", {}).get("mimeType", ""),
                    )
                )
        except Exception:
            logger.exception("Failed to list OneDrive items")
        return items

    async def get_file_content(self, drive_id: str, item_id: str) -> bytes:
        client = await self._get_http_client()
        response = await client.get(
            f"/drives/{drive_id}/items/{item_id}/content",
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.content

    async def aclose(self) -> None:
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
        self._msal_app = None
        self._access_token = None


DocumentSourceFactory.register("onedrive", OneDriveAdapter)
