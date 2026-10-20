import hashlib
import hmac
import json
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel

from eip.core.aws import enqueue, store_raw_payload
from eip.core.config import get_settings
from eip.core.redis import redis_client

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

DEDUPE_TTL_SECONDS = 24 * 60 * 60


class WebhookAccepted(BaseModel):
    status: str


def verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not secret or not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def accept(source: str, event: str, delivery_id: str, body: bytes) -> WebhookAccepted:
    dedupe_key = f"eip:webhook:{source}:{delivery_id}"
    if delivery_id and not await redis_client.set(dedupe_key, "1", nx=True, ex=DEDUPE_TTL_SECONDS):
        return WebhookAccepted(status="duplicate")
    try:
        s3_key = await store_raw_payload(source, body)
        await enqueue({"source": source, "event": event, "s3_key": s3_key})
    except Exception:
        if delivery_id:
            await redis_client.delete(dedupe_key)
        raise
    return WebhookAccepted(status="accepted")


@router.post("/github", status_code=status.HTTP_202_ACCEPTED, response_model=WebhookAccepted)
async def github_webhook(
    request: Request,
    x_hub_signature_256: Annotated[str | None, Header()] = None,
    x_github_event: Annotated[str, Header()] = "",
    x_github_delivery: Annotated[str, Header()] = "",
) -> WebhookAccepted:
    body = await request.body()
    secret = get_settings().github_webhook_secret.get_secret_value()
    if not verify_signature(secret, body, x_hub_signature_256):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
    return await accept("github", x_github_event, x_github_delivery, body)


@router.post("/jira", status_code=status.HTTP_202_ACCEPTED, response_model=WebhookAccepted)
async def jira_webhook(
    request: Request,
    x_hub_signature: Annotated[str | None, Header()] = None,
    x_atlassian_webhook_identifier: Annotated[str, Header()] = "",
) -> WebhookAccepted:
    body = await request.body()
    secret = get_settings().jira_webhook_secret.get_secret_value()
    if not verify_signature(secret, body, x_hub_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
    event = str(json.loads(body).get("webhookEvent", ""))
    return await accept("jira", event, x_atlassian_webhook_identifier, body)
