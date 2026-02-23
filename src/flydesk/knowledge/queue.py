# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Background queue for asynchronous knowledge document indexing.

Provides an in-memory queue (``asyncio.Queue``) and an optional Redis-backed
queue so that document indexing can happen outside the HTTP request cycle.
Both backends satisfy the ``QueueProducer`` / ``QueueConsumer`` protocols
from ``fireflyframework_genai.exposure.queues``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, Field

from fireflyframework_genai.exposure.queues import QueueMessage

logger = logging.getLogger(__name__)

INDEXING_QUEUE_NAME = "knowledge.indexing"


# ---------------------------------------------------------------------------
# Task model
# ---------------------------------------------------------------------------


class IndexingTask(BaseModel):
    """Describes a single document that needs to be indexed."""

    document_id: str
    title: str
    content: str
    document_type: str
    source: str = ""
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# In-memory backend
# ---------------------------------------------------------------------------


class InMemoryIndexingProducer:
    """Publish ``IndexingTask`` messages to an in-memory ``asyncio.Queue``.

    Satisfies the ``QueueProducer`` protocol.
    """

    def __init__(self, queue: asyncio.Queue[QueueMessage]) -> None:
        self._queue = queue

    async def publish(self, message: QueueMessage) -> None:
        await self._queue.put(message)
        logger.debug("Enqueued indexing task (queue size=%d)", self._queue.qsize())


class InMemoryIndexingConsumer:
    """Consume ``IndexingTask`` messages from an in-memory ``asyncio.Queue``.

    Satisfies the ``QueueConsumer`` protocol.
    """

    def __init__(
        self,
        queue: asyncio.Queue[QueueMessage],
        handler: Callable[[IndexingTask], Coroutine[Any, Any, None]],
    ) -> None:
        self._queue = queue
        self._handler = handler
        self._running = False
        self._task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Begin consuming messages in the background."""
        self._running = True
        self._task = asyncio.create_task(self._consume_loop())
        logger.info("In-memory indexing consumer started")

    async def stop(self) -> None:
        """Gracefully stop the consumer."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("In-memory indexing consumer stopped")

    async def _consume_loop(self) -> None:
        """Main consumer loop -- pulls messages and invokes the handler."""
        while self._running:
            try:
                message = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except (asyncio.TimeoutError, TimeoutError):
                continue
            except asyncio.CancelledError:
                break

            try:
                task = IndexingTask.model_validate_json(message.body)
                await self._handler(task)
                logger.info(
                    "Indexed document %s (%s)", task.document_id, task.title
                )
            except Exception:
                logger.exception(
                    "Failed to process indexing task from queue"
                )


# ---------------------------------------------------------------------------
# Redis backend
# ---------------------------------------------------------------------------


class RedisIndexingProducer:
    """Publish ``IndexingTask`` messages to a Redis list.

    Satisfies the ``QueueProducer`` protocol.
    """

    def __init__(self, url: str = "redis://localhost:6379") -> None:
        self._url = url
        self._client: Any = None

    async def start(self) -> None:
        import redis.asyncio as aioredis  # type: ignore[import-not-found]

        self._client = aioredis.from_url(self._url)
        logger.info("Redis indexing producer started (queue=%s)", INDEXING_QUEUE_NAME)

    async def publish(self, message: QueueMessage) -> None:
        if self._client is None:
            await self.start()
        await self._client.lpush(INDEXING_QUEUE_NAME, message.body)
        logger.debug("Enqueued indexing task to Redis")

    async def stop(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
        logger.info("Redis indexing producer stopped")


class RedisIndexingConsumer:
    """Consume ``IndexingTask`` messages from a Redis list (BRPOP).

    Satisfies the ``QueueConsumer`` protocol.
    """

    def __init__(
        self,
        handler: Callable[[IndexingTask], Coroutine[Any, Any, None]],
        url: str = "redis://localhost:6379",
    ) -> None:
        self._url = url
        self._handler = handler
        self._running = False
        self._client: Any = None
        self._task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        import redis.asyncio as aioredis  # type: ignore[import-not-found]

        self._client = aioredis.from_url(self._url)
        self._running = True
        self._task = asyncio.create_task(self._consume_loop())
        logger.info("Redis indexing consumer started (queue=%s)", INDEXING_QUEUE_NAME)

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._client:
            await self._client.close()
            self._client = None
        logger.info("Redis indexing consumer stopped")

    async def _consume_loop(self) -> None:
        while self._running:
            try:
                result = await self._client.brpop(INDEXING_QUEUE_NAME, timeout=1)
                if result is None:
                    continue
                _, raw = result
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")

                task = IndexingTask.model_validate_json(raw)
                await self._handler(task)
                logger.info(
                    "Indexed document %s (%s)", task.document_id, task.title
                )
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception(
                    "Failed to process indexing task from Redis queue"
                )


# ---------------------------------------------------------------------------
# High-level producer wrapper
# ---------------------------------------------------------------------------


class IndexingQueueProducer:
    """High-level producer that serialises ``IndexingTask`` into a
    ``QueueMessage`` and delegates to the underlying backend producer.
    """

    def __init__(self, producer: InMemoryIndexingProducer | RedisIndexingProducer) -> None:
        self._producer = producer

    async def enqueue(self, task: IndexingTask) -> None:
        """Serialise *task* and publish it to the indexing queue."""
        message = QueueMessage(
            body=task.model_dump_json(),
            routing_key=INDEXING_QUEUE_NAME,
        )
        await self._producer.publish(message)

    async def stop(self) -> None:
        """Shut down the underlying producer if it supports it."""
        if hasattr(self._producer, "stop"):
            await self._producer.stop()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_indexing_queue(
    backend: str,
    handler: Callable[[IndexingTask], Coroutine[Any, Any, None]],
    redis_url: str | None = None,
) -> tuple[IndexingQueueProducer, InMemoryIndexingConsumer | RedisIndexingConsumer]:
    """Create a matched producer/consumer pair for the given backend.

    Parameters:
        backend: ``"memory"`` or ``"redis"``.
        handler: Async callable invoked for each ``IndexingTask``.
        redis_url: Redis connection URL (required when *backend* is ``"redis"``).

    Returns:
        A ``(producer, consumer)`` tuple.
    """
    if backend == "redis":
        if not redis_url:
            raise ValueError("redis_url is required for the 'redis' queue backend")
        raw_producer = RedisIndexingProducer(url=redis_url)
        consumer = RedisIndexingConsumer(handler=handler, url=redis_url)
    else:
        queue: asyncio.Queue[QueueMessage] = asyncio.Queue()
        raw_producer = InMemoryIndexingProducer(queue)
        consumer = InMemoryIndexingConsumer(queue, handler=handler)

    producer = IndexingQueueProducer(raw_producer)
    return producer, consumer
