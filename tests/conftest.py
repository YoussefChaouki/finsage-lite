"""
Pytest Configuration and Fixtures

Shared fixtures for integration tests requiring a running Docker stack.
Session-scoped fixtures ensure API readiness before test execution.
"""

import os
import time
from collections.abc import Generator

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()  # .env → os.environ (no-op if file is missing)

_test_env = {
    "POSTGRES_USER": "finsage",
    "POSTGRES_PASSWORD": "finsage_password",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "5432",
    "POSTGRES_DB": "finsage_db",
    "EDGAR_USER_AGENT": "FinSage Test (test@example.com)",
}
for _key, _value in _test_env.items():
    os.environ.setdefault(_key, _value)

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="session")
def wait_for_api() -> None:
    """
    Block until the API is ready or timeout expires.

    Polls /health endpoint with 1s intervals for up to 30s.
    Fails the test session if API is unreachable (Docker likely not running).

    Scope:
        session - runs once before all tests that depend on it.
    """
    url = f"{BASE_URL}/health"
    timeout = 30
    start = time.time()

    print("\n[Test] Waiting for API...")
    while time.time() - start < timeout:
        try:
            res = httpx.get(url, timeout=1.0)
            if res.status_code == 200:
                print("API Ready")
                return
        except httpx.RequestError:
            time.sleep(1)

    pytest.fail("API unreachable. Docker is likely down.")


@pytest.fixture(scope="session")
def api_client(wait_for_api: None) -> Generator[httpx.Client, None, None]:
    """
    Pre-configured HTTP client for integration tests.

    Depends on wait_for_api to ensure API is ready.
    Base URL points to root for cleaner test assertions.

    Yields:
        httpx.Client: Session-scoped client, automatically closed after tests.
    """
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        yield client
