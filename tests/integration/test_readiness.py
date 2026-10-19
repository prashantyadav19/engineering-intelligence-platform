import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_readiness_reports_database_and_redis_ok(client: AsyncClient) -> None:
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"database": "ok", "redis": "ok"},
    }
