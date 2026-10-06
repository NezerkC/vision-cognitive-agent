"""
High-Performance In-Memory Async Event Bus for Visión OS.
Implements IEventBus using asynchronous queues and non-blocking worker dispatches.
"""

import asyncio
import fnmatch
import logging
import uuid
from typing import Any

from core.ports.event_bus import EventHandler, IEventBus

logger = logging.getLogger("InMemoryEventBus")


class AsyncInMemoryEventBus(IEventBus):
    """
    In-Memory Event Bus replacing the raw TCP broker with zero-overhead message passing.
    Eliminates Base64 JSON socket latency and cross-process serialization bottlenecks.
    """

    def __init__(self, max_queue_size: int = 500):
        self.max_queue_size = max_queue_size
        self._subscriptions: dict[str, dict[str, Any]] = {}  # sub_id -> {pattern, handler, queue, task}
        self._lock = asyncio.Lock()
        self._is_running = True

    async def publish(self, topic: str, data: dict[str, Any]) -> None:
        """
        Publishes an event to all matching subscribed queues.
        Dispatches non-blocking events with matching wildcard topics.
        """
        if not self._is_running:
            logger.warning(f"Event bus stopped. Dropping event on topic: {topic}")
            return

        async with self._lock:
            active_subs = list(self._subscriptions.values())

        matched_count = 0
        for sub in active_subs:
            pattern = sub["pattern"]
            # Match exact topic or wildcard pattern (e.g. canal.*, canal.sensorial.*)
            if pattern == "*" or pattern == topic or fnmatch.fnmatch(topic, pattern):
                queue: asyncio.Queue = sub["queue"]
                try:
                    queue.put_nowait((topic, data))
                    matched_count += 1
                except asyncio.QueueFull:
                    logger.warning(f"Queue full for subscription {sub['id']} on pattern '{pattern}'. Dropping event.")

        logger.debug(f"Published event on '{topic}' to {matched_count} matching subscriber(s).")

    async def subscribe(self, topics: list[str], handler: EventHandler) -> str:
        """
        Subscribes an async handler to one or more topic patterns.
        Spawns a dedicated consumer task for non-blocking execution.
        """
        sub_id = str(uuid.uuid4())
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.max_queue_size)

        for pattern in topics:
            pid = f"{sub_id}_{pattern}"
            consumer_task = asyncio.create_task(
                self._consumer_loop(pid, pattern, queue, handler), name=f"Consumer_{pid}"
            )
            async with self._lock:
                self._subscriptions[pid] = {
                    "id": pid,
                    "sub_id": sub_id,
                    "pattern": pattern,
                    "handler": handler,
                    "queue": queue,
                    "task": consumer_task,
                }
            logger.info(f"Subscribed handler to pattern '{pattern}' (ID: {pid})")

        return sub_id

    async def _consumer_loop(self, sub_id: str, pattern: str, queue: asyncio.Queue, handler: EventHandler) -> None:
        """Dedicated consumer worker executing subscriber handlers asynchronously."""
        while self._is_running:
            try:
                topic, data = await queue.get()
                try:
                    await handler(topic, data)
                except Exception as e:
                    logger.error(f"Error executing handler in subscription '{pattern}': {e}", exc_info=True)
                finally:
                    queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in consumer loop {sub_id}: {e}")

    async def unsubscribe(self, subscription_id: str) -> None:
        """Unregisters all topic patterns associated with a subscription ID."""
        async with self._lock:
            to_remove = [
                pid
                for pid, sub in self._subscriptions.items()
                if sub.get("sub_id") == subscription_id or pid == subscription_id
            ]
            for pid in to_remove:
                sub = self._subscriptions.pop(pid, None)
                if sub and sub.get("task"):
                    sub["task"].cancel()
                logger.info(f"Unsubscribed subscription ID: {pid}")

    async def purge(self) -> None:
        """Purges pending events across all queues."""
        async with self._lock:
            for sub in self._subscriptions.values():
                queue: asyncio.Queue = sub["queue"]
                while not queue.empty():
                    try:
                        queue.get_nowait()
                        queue.task_done()
                    except (asyncio.QueueEmpty, ValueError):
                        break
        logger.info("In-Memory Event Bus purged all queues.")

    async def shutdown(self) -> None:
        """Gracefully shuts down all consumer tasks."""
        self._is_running = False
        async with self._lock:
            for sub in self._subscriptions.values():
                if sub.get("task"):
                    sub["task"].cancel()
            self._subscriptions.clear()
        logger.info("In-Memory Event Bus shutdown complete.")
