from collections.abc import AsyncIterator
from typing import Any

import httpx

from eip.connectors.http import get_json

ISSUE_FIELDS = ["summary", "status", "issuetype", "assignee", "resolutiondate", "project"]


class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            auth=(email, api_token),
            headers={"Accept": "application/json"},
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def board_id(self, project_key: str) -> int | None:
        data = await get_json(self._client, "/rest/agile/1.0/board", {"projectKeyOrId": project_key})
        boards: list[dict[str, Any]] = data["values"]
        return int(boards[0]["id"]) if boards else None

    async def sprints(self, board_id: int) -> AsyncIterator[dict[str, Any]]:
        start_at = 0
        while True:
            page = await get_json(
                self._client,
                f"/rest/agile/1.0/board/{board_id}/sprint",
                {"startAt": start_at, "maxResults": 50},
            )
            for sprint in page["values"]:
                yield sprint
            if page.get("isLast", True):
                return
            start_at += len(page["values"])

    async def issues(self, project_key: str, updated_since: str, extra_fields: list[str]) -> AsyncIterator[dict[str, Any]]:
        jql = f'project = "{project_key}" AND updated >= "{updated_since}" ORDER BY updated ASC'
        next_page_token: str | None = None
        while True:
            params: dict[str, Any] = {
                "jql": jql,
                "fields": ",".join(ISSUE_FIELDS + extra_fields),
                "maxResults": 100,
            }
            if next_page_token:
                params["nextPageToken"] = next_page_token
            page = await get_json(self._client, "/rest/api/3/search/jql", params)
            for issue in page["issues"]:
                yield issue
            next_page_token = page.get("nextPageToken")
            if not next_page_token:
                return

    async def changelog(self, issue_key: str) -> AsyncIterator[dict[str, Any]]:
        start_at = 0
        while True:
            page = await get_json(
                self._client,
                f"/rest/api/3/issue/{issue_key}/changelog",
                {"startAt": start_at, "maxResults": 100},
            )
            for history in page["values"]:
                yield history
            if page.get("isLast", True):
                return
            start_at += len(page["values"])

    async def issue(self, issue_key: str, extra_fields: list[str]) -> dict[str, Any]:
        data: dict[str, Any] = await get_json(
            self._client,
            f"/rest/api/3/issue/{issue_key}",
            {"fields": ",".join(ISSUE_FIELDS + extra_fields)},
        )
        return data
