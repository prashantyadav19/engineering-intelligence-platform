from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from eip.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
