from collections.abc import AsyncIterator
from typing import Any

import httpx

from eip.connectors.http import get_json


class GitHubClient:
    def __init__(self, token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def pull_requests(self, repo: str) -> AsyncIterator[dict[str, Any]]:
        page = 1
        while True:
            batch: list[dict[str, Any]] = await get_json(
                self._client,
                f"/repos/{repo}/pulls",
                {"state": "all", "sort": "updated", "direction": "desc", "per_page": 100, "page": page},
            )
            if not batch:
                return
            for pull_request in batch:
                yield pull_request
            page += 1

    async def reviews(self, repo: str, number: int) -> list[dict[str, Any]]:
        reviews: list[dict[str, Any]] = await get_json(self._client, f"/repos/{repo}/pulls/{number}/reviews", {"per_page": 100})
        return reviews
