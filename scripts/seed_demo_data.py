import asyncio
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from eip.db.models import Issue, IssueEvent, IssuePullRequest, Project, PullRequest, Sprint
from eip.db.session import SessionLocal

DEMO_REPO = "demo/payments-platform"
SPRINT_DAYS = 14
SPRINT_COUNT = 6
RELEASE = "2.4"
POINTS = [1, 2, 3, 3, 5, 5, 8]
REVIEWERS = ["asha", "rahul", "meera", "vikram"]

TEAMS = {
    "PAY": {"name": "Payments", "first_issue": 401, "sprint_base": 900000, "spill_rate": 0.15},
    "CHK": {"name": "Checkout", "first_issue": 101, "sprint_base": 910000, "spill_rate": 0.30},
}

SUMMARIES = [
    "Add retry to payment gateway calls",
    "Show saved cards on checkout",
    "Refund status webhook handler",
    "Validate GST number on invoices",
    "Split payment across two cards",
    "Cache exchange rates for 10 minutes",
    "Audit log for refund approvals",
    "Improve error message on card decline",
    "Pagination on transaction history",
    "Rate-limit OTP requests",
    "Export settlements to CSV",
    "Add idempotency key to charge API",
]


class TeamBuilder:
    def __init__(self, key: str, rng: random.Random, now: datetime) -> None:
        config = TEAMS[key]
        self.key = key
        self.rng = rng
        self.now = now
        self.name = str(config["name"])
        self.next_issue = int(config["first_issue"])
        self.sprint_base = int(config["sprint_base"])
        self.spill_rate = float(config["spill_rate"])
        self.next_pr = 1 if key == "PAY" else 500
        self.event_count = 0

    def issue_key(self) -> str:
        key = f"{self.key}-{self.next_issue}"
        self.next_issue += 1
        return key

    def event(self, issue: Issue, field: str, old: str | None, new: str | None, at: datetime) -> IssueEvent:
        self.event_count += 1
        return IssueEvent(
            issue_id=issue.id,
            field=field,
            from_value=old,
            to_value=new,
            changed_at=at,
            external_id=f"demo:{issue.key}:{self.event_count}",
        )

    def pull_request(self, issue: Issue, opened: datetime, review_hours: float, merged: datetime | None) -> PullRequest:
        number = self.next_pr
        self.next_pr += 1
        first_review = opened + timedelta(hours=review_hours)
        return PullRequest(
            repo=DEMO_REPO,
            number=number,
            title=f"{issue.key} {issue.summary}",
            state="merged" if merged else "open",
            author=self.rng.choice(REVIEWERS),
            opened_at=opened,
            first_review_at=first_review if first_review < self.now else None,
            merged_at=merged,
        )

    async def build(self, session) -> None:  # type: ignore[no-untyped-def]
        project = Project(key=self.key, name=self.name)
        session.add(project)
        await session.flush()

        first_start = self.now - timedelta(days=SPRINT_DAYS * (SPRINT_COUNT - 1) + 7)
        sprints: list[Sprint] = []
        for number in range(SPRINT_COUNT):
            start = first_start + timedelta(days=number * SPRINT_DAYS)
            sprints.append(
                Sprint(
                    external_id=self.sprint_base + number,
                    project_id=project.id,
                    name=f"{self.key} Sprint {number + 1}",
                    state="active" if number == SPRINT_COUNT - 1 else "closed",
                    start_at=start,
                    end_at=start + timedelta(days=SPRINT_DAYS),
                )
            )
        session.add_all(sprints)
        await session.flush()

        for index, sprint in enumerate(sprints):
            is_active = sprint.state == "active"
            next_sprint = sprints[index + 1] if index + 1 < len(sprints) else None
            for _ in range(self.rng.randint(8, 11)):
                await self.story(session, project, sprint, next_sprint, is_active)

        for _ in range(8):
            issue = Issue(
                key=self.issue_key(),
                project_id=project.id,
                sprint_id=None,
                summary=self.rng.choice(SUMMARIES),
                issue_type="Story",
                status="To Do",
                story_points=float(self.rng.choice(POINTS)),
                fix_version=RELEASE,
            )
            session.add(issue)

    async def story(  # type: ignore[no-untyped-def]
        self, session, project: Project, sprint: Sprint, next_sprint: Sprint | None, is_active: bool
    ) -> None:
        assert sprint.start_at is not None and sprint.end_at is not None
        start, end = sprint.start_at, sprint.end_at
        points = float(self.rng.choice(POINTS))
        spills = not is_active and self.rng.random() < self.spill_rate
        issue = Issue(
            key=self.issue_key(),
            project_id=project.id,
            sprint_id=sprint.id,
            summary=self.rng.choice(SUMMARIES),
            issue_type="Story",
            status="To Do",
            story_points=points,
            fix_version=RELEASE if is_active or (spills and next_sprint is not None) else None,
        )
        session.add(issue)
        await session.flush()
        events: list[IssueEvent] = []

        started = start + timedelta(days=self.rng.uniform(6, 9) if spills else self.rng.uniform(0, 4))
        if is_active and started > self.now:
            session.add_all(events)
            return
        events.append(self.event(issue, "status", "To Do", "In Progress", started))
        issue.status = "In Progress"

        opened = started + timedelta(days=self.rng.uniform(1, 3))
        review_hours = self.rng.uniform(30, 50) if spills else self.rng.uniform(2, 20)
        if opened > self.now:
            session.add_all(events)
            return
        events.append(self.event(issue, "status", "In Progress", "In Review", opened))
        issue.status = "In Review"

        if spills and next_sprint is not None:
            events.append(self.event(issue, "sprint", sprint.name, next_sprint.name, end))
            issue.sprint_id = next_sprint.id
            done = end + timedelta(days=self.rng.uniform(1, 4))
        else:
            done = min(opened + timedelta(hours=review_hours, days=self.rng.uniform(0.2, 1.5)), end - timedelta(hours=6))

        merged = done if done < self.now else None
        pull_request = self.pull_request(issue, opened, review_hours, merged)
        session.add(pull_request)
        await session.flush()
        session.add(IssuePullRequest(issue_id=issue.id, pull_request_id=pull_request.id))

        if merged is not None:
            events.append(self.event(issue, "status", "In Review", "Done", done))
            issue.status = "Done"
            issue.resolved_at = done
        session.add_all(events)


async def plant_pay_482(session, now: datetime) -> None:  # type: ignore[no-untyped-def]
    sprint_5 = (await session.execute(select(Sprint).where(Sprint.name == "PAY Sprint 5"))).scalar_one()
    sprint_6 = (await session.execute(select(Sprint).where(Sprint.name == "PAY Sprint 6"))).scalar_one()
    start, end = sprint_5.start_at, sprint_5.end_at

    issue = Issue(
        key="PAY-482",
        project_id=sprint_5.project_id,
        sprint_id=sprint_6.id,
        summary="Add UPI autopay mandate support",
        issue_type="Story",
        status="In Review",
        story_points=5.0,
        fix_version=RELEASE,
    )
    session.add(issue)
    await session.flush()

    def event(field: str, old: str | None, new: str | None, day: float, n: int) -> IssueEvent:
        return IssueEvent(
            issue_id=issue.id,
            field=field,
            from_value=old,
            to_value=new,
            changed_at=start + timedelta(days=day),
            external_id=f"demo:PAY-482:{n}",
        )

    session.add_all(
        [
            event("status", "To Do", "In Progress", 2, 1),
            event("status", "In Progress", "Blocked", 4, 2),
            event("story_points", "3", "5", 6, 3),
            event("status", "Blocked", "In Progress", 7, 4),
            event("status", "In Progress", "In Review", 8, 5),
            event("sprint", "PAY Sprint 5", "PAY Sprint 6", (end - start).days, 6),
        ]
    )
    pull_request = PullRequest(
        repo=DEMO_REPO,
        number=1182,
        title="PAY-482 UPI autopay mandate",
        state="open",
        author="rahul",
        opened_at=start + timedelta(days=8),
        first_review_at=start + timedelta(days=8, hours=41),
        merged_at=None,
    )
    session.add(pull_request)
    await session.flush()
    session.add(IssuePullRequest(issue_id=issue.id, pull_request_id=pull_request.id))


async def reset(session) -> None:  # type: ignore[no-untyped-def]
    project_ids = select(Project.id).where(Project.key.in_(TEAMS.keys()))
    await session.execute(delete(Issue).where(Issue.project_id.in_(project_ids)))
    await session.execute(delete(Sprint).where(Sprint.project_id.in_(project_ids)))
    await session.execute(delete(PullRequest).where(PullRequest.repo == DEMO_REPO))
    await session.execute(delete(Project).where(Project.key.in_(TEAMS.keys())))


async def main() -> None:
    rng = random.Random(42)
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        await reset(session)
        for key in TEAMS:
            await TeamBuilder(key, rng, now).build(session)
        await plant_pay_482(session, now)
        await session.commit()
    print("Demo data loaded: teams PAY and CHK, 6 sprints each, release 2.4, story PAY-482")


if __name__ == "__main__":
    asyncio.run(main())
