import argparse
import asyncio
from datetime import date, timedelta

from eip.core.config import get_settings
from eip.ingestion.service import (
    jira_extra_fields,
    make_github_client,
    make_jira_client,
    store_issue,
    store_pull_request,
)


async def sync_jira(since: str) -> int:
    jira = make_jira_client()
    count = 0
    try:
        for project_key in get_settings().jira_project_keys:
            async for issue in jira.issues(project_key, since, jira_extra_fields()):
                await store_issue(jira, issue)
                count += 1
    finally:
        await jira.close()
    return count


async def sync_github() -> int:
    github = make_github_client()
    count = 0
    try:
        for repo in get_settings().github_repos:
            async for pr in github.pull_requests(repo):
                await store_pull_request(github, repo, pr)
                count += 1
    finally:
        await github.close()
    return count


async def run(since: str) -> None:
    issues = await sync_jira(since)
    print(f"Jira: stored {issues} issues")
    pull_requests = await sync_github()
    print(f"GitHub: stored {pull_requests} pull requests")


def main() -> None:
    default_since = (date.today() - timedelta(days=365)).isoformat()
    parser = argparse.ArgumentParser(description="Sync Jira and GitHub data into EIP")
    parser.add_argument("--since", default=default_since, help="YYYY-MM-DD")
    args = parser.parse_args()
    asyncio.run(run(args.since))


if __name__ == "__main__":
    main()
