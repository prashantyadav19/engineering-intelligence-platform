import asyncio
import json
import logging
from typing import Any

from eip.connectors.github import GitHubClient
from eip.connectors.jira import JiraClient
from eip.core.aws import ingest_queue_url, read_raw_payload, sqs_client
from eip.ingestion.service import (
    make_github_client,
    make_jira_client,
    store_issue_by_key,
    store_pull_request,
)

logger = logging.getLogger("eip.worker")


async def process(message: dict[str, str], jira: JiraClient, github: GitHubClient) -> None:
    payload: dict[str, Any] = json.loads(await read_raw_payload(message["s3_key"]))
    if message["source"] == "jira":
        issue_key = (payload.get("issue") or {}).get("key")
        if issue_key:
            await store_issue_by_key(jira, issue_key)
    elif message["source"] == "github" and "pull_request" in payload:
        repo = payload["repository"]["full_name"]
        await store_pull_request(github, repo, payload["pull_request"])


def _receive() -> list[dict[str, Any]]:
    response = sqs_client().receive_message(QueueUrl=ingest_queue_url(), MaxNumberOfMessages=10, WaitTimeSeconds=20)
    return [dict(message) for message in response.get("Messages", [])]


def _delete(receipt_handle: str) -> None:
    sqs_client().delete_message(QueueUrl=ingest_queue_url(), ReceiptHandle=receipt_handle)


async def run() -> None:
    jira = make_jira_client()
    github = make_github_client()
    logger.info("Worker started, waiting for messages")
    try:
        while True:
            for message in await asyncio.to_thread(_receive):
                try:
                    await process(json.loads(message["Body"]), jira, github)
                except Exception:
                    logger.exception("Processing failed; SQS will retry the message")
                    continue
                await asyncio.to_thread(_delete, message["ReceiptHandle"])
                logger.info("Processed message %s", message["MessageId"])
    finally:
        await jira.close()
        await github.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(run())
