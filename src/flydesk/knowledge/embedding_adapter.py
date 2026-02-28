# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Adapter bridging fireflyframework-genai embedders to the local EmbeddingProvider protocol."""

from __future__ import annotations

from typing import Any

from fireflyframework_genai.embeddings import BaseEmbedder


class GenAIEmbeddingAdapter:
    """Adapts a fireflyframework-genai BaseEmbedder to the EmbeddingProvider protocol."""

    def __init__(self, embedder: BaseEmbedder) -> None:
        self._embedder = embedder

    async def embed(self, texts: list[str]) -> list[list[float]]:
        result = await self._embedder.embed(texts)
        return result.embeddings

    async def check_status(self) -> dict[str, Any]:
        """Health check via a single embedding call."""
        try:
            result = await self._embedder.embed(["health check"])
            dims = len(result.embeddings[0]) if result.embeddings else 0
            is_zero = all(v == 0.0 for v in result.embeddings[0]) if dims else True
            return {
                "status": "warning" if is_zero else "ok",
                "dimensions": dims,
                "message": "Zero vector (missing API key?)" if is_zero else "OK",
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc), "dimensions": 0}
