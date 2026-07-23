"""Shared fixtures for Visión OS test suite."""
import asyncio

import pytest


@pytest.fixture
def event_loop():
    """Provides a fresh event loop per test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_broker_config():
    """Provides test broker network configuration."""
    return {"host": "127.0.0.1", "port": 0}
