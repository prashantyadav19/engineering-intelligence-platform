import asyncio

from eip.connectors.github import GitHubClient
from eip.connectors.jira import JiraClient
from eip.core.config import get_settings


async def main() -> None:
    settings = get_settings()

    jira = JiraClient(settings.jira_base_url, settings.jira_email, settings.jira_api_token.get_secret_value())
    try:
        for project_key in settings.jira_project_keys:
            board = await jira.board_id(project_key)
            print(f"Jira project {project_key}: board {board}")
            count = 0
            async for _issue in jira.issues(project_key, "2000-01-01", []):
                count += 1
            print(f"  issues: {count}")
    finally:
        await jira.close()

    github = GitHubClient(settings.github_token.get_secret_value())
    try:
        for repo in settings.github_repos:
            count = 0
            async for _pull_request in github.pull_requests(repo):
                count += 1
            print(f"GitHub {repo}: {count} pull requests")
    finally:
        await github.close()


if __name__ == "__main__":
    asyncio.run(main())
