import httpx
import pytest

from eip.connectors.http import get_json


async def test_get_json_retries_on_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"ok": True})

    async def no_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr("eip.connectors.http.asyncio.sleep", no_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://x") as client:
        result = await get_json(client, "/thing")

    assert result == {"ok": True}
    assert calls["count"] == 2


async def test_get_json_does_not_retry_client_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://x") as client:
        with pytest.raises(httpx.HTTPStatusError):
            await get_json(client, "/missing")
