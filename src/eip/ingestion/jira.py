from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from eip.db.models import Issue, IssueEvent, Project, Sprint
from eip.ingestion.parsing import parse_datetime

TRACKED_FIELDS = {
    "status": "status",
    "sprint": "sprint",
    "assignee": "assignee",
    "story points": "story_points",
    "story point estimate": "story_points",
}


async def upsert_project(session: AsyncSession, key: str, name: str) -> int:
    stmt = insert(Project).values(key=key, name=name)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Project.key],
        set_={"name": stmt.excluded.name, "updated_at": func.now()},
    )
    project_id: int = (await session.execute(stmt.returning(Project.id))).scalar_one()
    return project_id


async def upsert_sprint(session: AsyncSession, project_id: int, sprint: dict[str, Any]) -> int:
    stmt = insert(Sprint).values(
        external_id=int(sprint["id"]),
        project_id=project_id,
        name=sprint["name"],
        state=sprint["state"],
        start_at=parse_datetime(sprint.get("startDate")),
        end_at=parse_datetime(sprint.get("endDate")),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Sprint.external_id],
        set_={
            "name": stmt.excluded.name,
            "state": stmt.excluded.state,
            "start_at": stmt.excluded.start_at,
            "end_at": stmt.excluded.end_at,
            "updated_at": func.now(),
        },
    )
    sprint_id: int = (await session.execute(stmt.returning(Sprint.id))).scalar_one()
    return sprint_id


def current_sprint(sprints: list[dict[str, Any]]) -> dict[str, Any] | None:
    active = [sprint for sprint in sprints if sprint.get("state") == "active"]
    if active:
        return active[0]
    return sprints[-1] if sprints else None


async def ingest_issue(
    session: AsyncSession,
    issue: dict[str, Any],
    changelog: list[dict[str, Any]],
    sprint_field: str,
    points_field: str,
) -> None:
    fields = issue["fields"]
    project_id = await upsert_project(session, fields["project"]["key"], fields["project"]["name"])

    sprints: list[dict[str, Any]] = fields.get(sprint_field) or []
    current = current_sprint(sprints)
    sprint_id: int | None = None
    for sprint in sprints:
        stored_id = await upsert_sprint(session, project_id, sprint)
        if sprint is current:
            sprint_id = stored_id

    assignee = fields.get("assignee") or {}
    stmt = insert(Issue).values(
        key=issue["key"],
        project_id=project_id,
        sprint_id=sprint_id,
        summary=fields["summary"],
        issue_type=fields["issuetype"]["name"],
        status=fields["status"]["name"],
        story_points=fields.get(points_field),
        assignee=assignee.get("displayName"),
        resolved_at=parse_datetime(fields.get("resolutiondate")),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Issue.key],
        set_={
            "sprint_id": stmt.excluded.sprint_id,
            "summary": stmt.excluded.summary,
            "issue_type": stmt.excluded.issue_type,
            "status": stmt.excluded.status,
            "story_points": stmt.excluded.story_points,
            "assignee": stmt.excluded.assignee,
            "resolved_at": stmt.excluded.resolved_at,
            "updated_at": func.now(),
        },
    )
    issue_id: int = (await session.execute(stmt.returning(Issue.id))).scalar_one()

    rows: list[dict[str, Any]] = []
    for history in changelog:
        for index, item in enumerate(history["items"]):
            field = TRACKED_FIELDS.get(str(item.get("field", "")).lower())
            if field is None:
                continue
            rows.append(
                {
                    "issue_id": issue_id,
                    "field": field,
                    "from_value": item.get("fromString"),
                    "to_value": item.get("toString"),
                    "changed_at": parse_datetime(history["created"]),
                    "external_id": f"{history['id']}:{index}",
                }
            )
    if rows:
        await session.execute(insert(IssueEvent).values(rows).on_conflict_do_nothing(index_elements=[IssueEvent.external_id]))
