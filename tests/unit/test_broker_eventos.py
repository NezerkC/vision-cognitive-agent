"""Unit tests for EventBroker TCP bus."""
import pytest
from core.broker_eventos import EventBroker
from core.schemas import EventEnvelope


@pytest.mark.unit
def test_event_envelope_validation():
    """EventEnvelope validates incoming payload structure."""
    envelope = EventEnvelope.validate_payload(
        topic="canal.memoria",
        data={"action": "guardar", "text": "Test memory"}
    )
    assert envelope.topic == "canal.memoria"
    assert envelope.data["action"] == "guardar"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_broker_instantiation():
    """EventBroker initializes with correct host and port."""
    broker = EventBroker(host="127.0.0.1", port=0)
    assert broker.host == "127.0.0.1"
    assert broker.subscriptions == {}
