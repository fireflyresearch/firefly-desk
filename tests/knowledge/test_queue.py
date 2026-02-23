# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for the background knowledge indexing queue."""

from __future__ import annotations

import asyncio

import pytest

from flydesk.knowledge.queue import (
    INDEXING_QUEUE_NAME,
    InMemoryIndexingConsumer,
    InMemoryIndexingProducer,
    IndexingQueueProducer,
    IndexingTask,
    create_indexing_queue,
)
from fireflyframework_genai.exposure.queues import QueueMessage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_task() -> IndexingTask:
    return IndexingTask(
        document_id="doc-001",
        title="Test Document",
        content="Some content to index for testing purposes.",
        document_type="manual",
        source="test",
        tags=["test"],
        metadata={"version": "1.0"},
    )


@pytest.fixture
def memory_queue() -> asyncio.Queue[QueueMessage]:
    return asyncio.Queue()


@pytest.fixture
def memory_producer(memory_queue: asyncio.Queue[QueueMessage]) -> InMemoryIndexingProducer:
    return InMemoryIndexingProducer(memory_queue)


# ---------------------------------------------------------------------------
# IndexingTask tests
# ---------------------------------------------------------------------------


class TestIndexingTask:
    def test_serialise_round_trip(self, sample_task: IndexingTask):
        """IndexingTask serialises to JSON and back without loss."""
        json_str = sample_task.model_dump_json()
        restored = IndexingTask.model_validate_json(json_str)

        assert restored.document_id == sample_task.document_id
        assert restored.title == sample_task.title
        assert restored.content == sample_task.content
        assert restored.document_type == sample_task.document_type
        assert restored.source == sample_task.source
        assert restored.tags == sample_task.tags
        assert restored.metadata == sample_task.metadata

    def test_default_values(self):
        """Optional fields have sensible defaults."""
        task = IndexingTask(
            document_id="d1",
            title="T",
            content="C",
            document_type="other",
        )
        assert task.source == ""
        assert task.tags == []
        assert task.metadata == {}


# ---------------------------------------------------------------------------
# InMemoryIndexingProducer tests
# ---------------------------------------------------------------------------


class TestInMemoryIndexingProducer:
    async def test_publish_puts_message_on_queue(
        self,
        memory_producer: InMemoryIndexingProducer,
        memory_queue: asyncio.Queue[QueueMessage],
    ):
        """Publishing a QueueMessage places it on the underlying asyncio queue."""
        msg = QueueMessage(body='{"test": true}', routing_key="test.key")
        await memory_producer.publish(msg)

        assert memory_queue.qsize() == 1
        retrieved = memory_queue.get_nowait()
        assert retrieved.body == '{"test": true}'

    async def test_multiple_publishes(
        self,
        memory_producer: InMemoryIndexingProducer,
        memory_queue: asyncio.Queue[QueueMessage],
    ):
        """Multiple publishes are all enqueued."""
        for i in range(5):
            await memory_producer.publish(QueueMessage(body=str(i)))

        assert memory_queue.qsize() == 5


# ---------------------------------------------------------------------------
# InMemoryIndexingConsumer tests
# ---------------------------------------------------------------------------


class TestInMemoryIndexingConsumer:
    async def test_consumer_processes_task(
        self,
        memory_queue: asyncio.Queue[QueueMessage],
        sample_task: IndexingTask,
    ):
        """Consumer invokes the handler with a deserialised IndexingTask."""
        processed: list[IndexingTask] = []

        async def handler(task: IndexingTask) -> None:
            processed.append(task)

        consumer = InMemoryIndexingConsumer(memory_queue, handler=handler)

        # Enqueue a message directly
        msg = QueueMessage(body=sample_task.model_dump_json())
        await memory_queue.put(msg)

        await consumer.start()

        # Allow the consumer loop to process
        await asyncio.sleep(0.1)
        await consumer.stop()

        assert len(processed) == 1
        assert processed[0].document_id == "doc-001"
        assert processed[0].title == "Test Document"

    async def test_consumer_handles_multiple_tasks(
        self,
        memory_queue: asyncio.Queue[QueueMessage],
    ):
        """Consumer processes multiple queued tasks sequentially."""
        processed: list[str] = []

        async def handler(task: IndexingTask) -> None:
            processed.append(task.document_id)

        consumer = InMemoryIndexingConsumer(memory_queue, handler=handler)

        for i in range(3):
            task = IndexingTask(
                document_id=f"doc-{i:03d}",
                title=f"Doc {i}",
                content=f"Content {i}",
                document_type="other",
            )
            await memory_queue.put(QueueMessage(body=task.model_dump_json()))

        await consumer.start()
        await asyncio.sleep(0.2)
        await consumer.stop()

        assert processed == ["doc-000", "doc-001", "doc-002"]

    async def test_consumer_survives_handler_error(
        self,
        memory_queue: asyncio.Queue[QueueMessage],
    ):
        """Consumer continues processing even if the handler raises."""
        processed: list[str] = []
        call_count = 0

        async def handler(task: IndexingTask) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated failure")
            processed.append(task.document_id)

        consumer = InMemoryIndexingConsumer(memory_queue, handler=handler)

        # Enqueue two tasks -- the first will fail, the second should succeed
        for doc_id in ("fail-doc", "ok-doc"):
            task = IndexingTask(
                document_id=doc_id,
                title="T",
                content="C",
                document_type="other",
            )
            await memory_queue.put(QueueMessage(body=task.model_dump_json()))

        await consumer.start()
        await asyncio.sleep(0.2)
        await consumer.stop()

        assert processed == ["ok-doc"]

    async def test_start_stop_lifecycle(
        self,
        memory_queue: asyncio.Queue[QueueMessage],
    ):
        """Consumer can be started and stopped cleanly."""

        async def noop_handler(task: IndexingTask) -> None:
            pass

        consumer = InMemoryIndexingConsumer(memory_queue, handler=noop_handler)

        assert not consumer.is_running
        await consumer.start()
        assert consumer.is_running
        await consumer.stop()
        assert not consumer.is_running


# ---------------------------------------------------------------------------
# IndexingQueueProducer (high-level wrapper) tests
# ---------------------------------------------------------------------------


class TestIndexingQueueProducer:
    async def test_enqueue_serialises_task(
        self,
        memory_producer: InMemoryIndexingProducer,
        memory_queue: asyncio.Queue[QueueMessage],
        sample_task: IndexingTask,
    ):
        """enqueue() serialises the task and publishes via the backend producer."""
        producer = IndexingQueueProducer(memory_producer)
        await producer.enqueue(sample_task)

        assert memory_queue.qsize() == 1
        msg = memory_queue.get_nowait()
        assert msg.routing_key == INDEXING_QUEUE_NAME

        # Deserialise and verify
        restored = IndexingTask.model_validate_json(msg.body)
        assert restored.document_id == sample_task.document_id

    async def test_stop_delegates_to_backend(self):
        """stop() calls stop on a backend that supports it."""
        stopped = False

        class FakeProducer:
            async def publish(self, message: QueueMessage) -> None:
                pass

            async def stop(self) -> None:
                nonlocal stopped
                stopped = True

        producer = IndexingQueueProducer(FakeProducer())  # type: ignore[arg-type]
        await producer.stop()
        assert stopped


# ---------------------------------------------------------------------------
# create_indexing_queue factory tests
# ---------------------------------------------------------------------------


class TestCreateIndexingQueue:
    def test_memory_backend(self):
        """Factory returns in-memory producer and consumer."""

        async def noop(task: IndexingTask) -> None:
            pass

        producer, consumer = create_indexing_queue(backend="memory", handler=noop)

        assert isinstance(producer, IndexingQueueProducer)
        assert isinstance(consumer, InMemoryIndexingConsumer)

    def test_redis_backend_requires_url(self):
        """Factory raises if redis backend is chosen without a URL."""

        async def noop(task: IndexingTask) -> None:
            pass

        with pytest.raises(ValueError, match="redis_url is required"):
            create_indexing_queue(backend="redis", handler=noop, redis_url=None)

    async def test_end_to_end_memory_queue(self, sample_task: IndexingTask):
        """Full round-trip: enqueue via producer, consumer processes it."""
        processed: list[IndexingTask] = []

        async def handler(task: IndexingTask) -> None:
            processed.append(task)

        producer, consumer = create_indexing_queue(backend="memory", handler=handler)
        await consumer.start()

        await producer.enqueue(sample_task)

        # Give the consumer time to process
        await asyncio.sleep(0.15)
        await consumer.stop()

        assert len(processed) == 1
        assert processed[0].document_id == sample_task.document_id
        assert processed[0].title == sample_task.title
        assert processed[0].content == sample_task.content
