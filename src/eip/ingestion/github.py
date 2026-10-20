from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from eip.db.models import Issue, IssuePullRequest, PullRequest
from eip.ingestion.parsing import extract_issue_keys, parse_datetime


def first_review_time(reviews: list[dict[str, Any]]) -> datetime | None:
    times = [parse_datetime(review.get("submitted_at")) for review in reviews]
    submitted = [time for time in times if time is not None]
    return min(submitted) if submitted else None


async def ingest_pull_request(session: AsyncSession, repo: str, pr: dict[str, Any], reviews: list[dict[str, Any]]) -> None:
    stmt = insert(PullRequest).values(
        repo=repo,
        number=int(pr["number"]),
        title=pr["title"],
        state="merged" if pr.get("merged_at") else pr["state"],
        author=(pr.get("user") or {}).get("login"),
        opened_at=parse_datetime(pr["created_at"]),
        first_review_at=first_review_time(reviews),
        merged_at=parse_datetime(pr.get("merged_at")),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["repo", "number"],
        set_={
            "title": stmt.excluded.title,
            "state": stmt.excluded.state,
            "first_review_at": stmt.excluded.first_review_at,
            "merged_at": stmt.excluded.merged_at,
            "updated_at": func.now(),
        },
    )
    pr_id: int = (await session.execute(stmt.returning(PullRequest.id))).scalar_one()

    keys = extract_issue_keys(pr.get("title"), pr.get("body"), (pr.get("head") or {}).get("ref"))
    if not keys:
        return
    issue_ids = (await session.execute(select(Issue.id).where(Issue.key.in_(keys)))).scalars().all()
    if issue_ids:
        await session.execute(insert(IssuePullRequest).values([{"issue_id": issue_id, "pull_request_id": pr_id} for issue_id in issue_ids]).on_conflict_do_nothing())
