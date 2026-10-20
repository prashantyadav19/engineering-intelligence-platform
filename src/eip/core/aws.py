import asyncio
import json
from datetime import UTC, datetime
from functools import lru_cache
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import boto3

from eip.core.config import get_settings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_sqs import SQSClient


def _client_options() -> dict[str, Any]:
    settings = get_settings()
    options: dict[str, Any] = {"region_name": settings.aws_region}
    if settings.aws_endpoint_url:
        options["endpoint_url"] = settings.aws_endpoint_url
        options["aws_access_key_id"] = "test"
        options["aws_secret_access_key"] = "test"
    return options


@lru_cache
def s3_client() -> "S3Client":
    return boto3.client("s3", **_client_options())


@lru_cache
def sqs_client() -> "SQSClient":
    return boto3.client("sqs", **_client_options())


@lru_cache
def ingest_queue_url() -> str:
    return sqs_client().get_queue_url(QueueName=get_settings().ingest_queue_name)["QueueUrl"]


def _raw_payload_key(source: str) -> str:
    return f"{source}/{datetime.now(UTC):%Y/%m/%d}/{uuid4()}.json"


async def store_raw_payload(source: str, body: bytes) -> str:
    key = _raw_payload_key(source)
    await asyncio.to_thread(
        s3_client().put_object,
        Bucket=get_settings().raw_payload_bucket,
        Key=key,
        Body=body,
        ContentType="application/json",
    )
    return key


def _read_object(key: str) -> bytes:
    response = s3_client().get_object(Bucket=get_settings().raw_payload_bucket, Key=key)
    return response["Body"].read()


async def read_raw_payload(key: str) -> bytes:
    return await asyncio.to_thread(_read_object, key)


def _send_message(body: str) -> None:
    sqs_client().send_message(QueueUrl=ingest_queue_url(), MessageBody=body)


async def enqueue(message: dict[str, str]) -> None:
    await asyncio.to_thread(_send_message, json.dumps(message))
