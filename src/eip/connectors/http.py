import asyncio
import random
from typing import Any

import httpx

RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 5


async def get_json(client: httpx.AsyncClient, path: str, params: dict[str, Any] | None = None) -> Any:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await client.get(path, params=params)
        except httpx.TransportError:
            if attempt == MAX_ATTEMPTS:
                raise
            await asyncio.sleep(backoff_seconds(attempt))
            continue

        if response.status_code not in RETRY_STATUSES:
            response.raise_for_status()
            return response.json()
        if attempt == MAX_ATTEMPTS:
            response.raise_for_status()
        await asyncio.sleep(retry_delay(response, attempt))

    raise RuntimeError(f"GET {path} failed after {MAX_ATTEMPTS} attempts")


def retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None and retry_after.isdigit():
        return float(retry_after)
    return backoff_seconds(attempt)


def backoff_seconds(attempt: int) -> float:
    return min(2.0**attempt, 30.0) + random.uniform(0, 1)
