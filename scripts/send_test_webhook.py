import hashlib
import hmac
import json
import sys
from uuid import uuid4

import httpx

from eip.core.config import get_settings


def main() -> None:
    issue_key = sys.argv[1]
    body = json.dumps({"webhookEvent": "jira:issue_updated", "issue": {"key": issue_key}}).encode()
    secret = get_settings().jira_webhook_secret.get_secret_value()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    delivery_id = str(uuid4())
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature": signature,
        "X-Atlassian-Webhook-Identifier": delivery_id,
    }

    for attempt in (1, 2):
        response = httpx.post("http://127.0.0.1:8000/webhooks/jira", content=body, headers=headers)
        print(f"Attempt {attempt}: {response.status_code} {response.json()}")


if __name__ == "__main__":
    main()
