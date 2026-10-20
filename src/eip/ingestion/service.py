from typing import Any

from eip.connectors.github import GitHubClient
from eip.connectors.jira import JiraClient
from eip.core.config import get_settings
from eip.db.session import SessionLocal
from eip.ingestion.github import ingest_pull_request
from eip.ingestion.jira import ingest_issue


def make_jira_client() -> JiraClient:
    settings = get_settings()
    return JiraClient(settings.jira_base_url, settings.jira_email, settings.jira_api_token.get_secret_value())


def make_github_client() -> GitHubClient:
    return GitHubClient(get_settings().github_token.get_secret_value())


def jira_extra_fields() -> list[str]:
    settings = get_settings()
    return [settings.jira_story_points_field, settings.jira_sprint_field]


async def store_issue(jira: JiraClient, issue: dict[str, Any]) -> None:
    settings = get_settings()
    changelog = [history async for history in jira.changelog(issue["key"])]
    async with SessionLocal() as session:
        await ingest_issue(session, issue, changelog, settings.jira_sprint_field, settings.jira_story_points_field)
        await session.commit()


async def store_issue_by_key(jira: JiraClient, issue_key: str) -> None:
    issue = await jira.issue(issue_key, jira_extra_fields())
    await store_issue(jira, issue)


async def store_pull_request(github: GitHubClient, repo: str, pr: dict[str, Any]) -> None:
    reviews = await github.reviews(repo, int(pr["number"]))
    async with SessionLocal() as session:
        await ingest_pull_request(session, repo, pr, reviews)
        await session.commit()
