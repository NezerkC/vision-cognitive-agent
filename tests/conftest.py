"""Shared fixtures for Visión OS test suite."""

import asyncio

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run the tests marked 'integration' (they need the network or running services).",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return
    skip_integration = pytest.mark.skip(reason="integration test: run pytest with --run-integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


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
