"""
Port specification for the Event Bus in Visión OS.
"""

from typing import Any, Awaitable, Callable, Protocol

EventHandler = Callable[[str, dict[str, Any]], Awaitable[None]]


class IEventBus(Protocol):
    """
    Abstract Event Bus port supporting pub/sub, wildcards, and clean async dispatch.
    """

    async def publish(self, topic: str, data: dict[str, Any]) -> None:
        """Publish an event payload to a specified topic."""
        ...

    async def subscribe(self, topics: list[str], handler: EventHandler) -> str:
        """
        Subscribe a handler to one or more topics.
        Returns a subscription identifier for unsubscription.
        """
        ...

    async def unsubscribe(self, subscription_id: str) -> None:
        """Unregister a subscription by its ID."""
        ...

    async def purge(self) -> None:
        """Purge internal queues and reset active message channels."""
        ...
