# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Content extraction from uploaded files."""

from __future__ import annotations


class ContentExtractor:
    """Extract text content from uploaded files."""

    async def extract(
        self, filename: str, content: bytes, content_type: str
    ) -> str | None:
        """Extract text content from a file.

        Returns the extracted text for supported types, or ``None`` for
        binary formats that require additional libraries (PDF, images, etc.).
        """
        if content_type.startswith("text/"):
            return content.decode("utf-8", errors="replace")
        if content_type == "application/json":
            return content.decode("utf-8", errors="replace")
        # For PDF, CSV, images -- return None (can be extended later)
        return None
