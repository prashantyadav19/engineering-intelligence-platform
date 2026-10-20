from eip.api.routes.webhooks import verify_signature
from eip.ingestion.jira import current_sprint
from eip.ingestion.parsing import extract_issue_keys

SECRET = "test-secret"
SIGNED_BODY = b'{"hello":"world"}'
VALID_SIGNATURE = "sha256=2f3e6a4a4b7a2bd2e3b8f2e1a1f0f63e9c1e7b0b0d1c5b1d6a2f9d6c2f2d1a0e"


def test_extract_issue_keys_finds_keys_in_title_and_branch() -> None:
    keys = extract_issue_keys("EIP-12 add login", None, "feature/eip-7-cache")

    assert keys == {"EIP-12", "EIP-7"}


def test_verify_signature_accepts_matching_hmac() -> None:
    import hashlib
    import hmac

    signature = "sha256=" + hmac.new(SECRET.encode(), SIGNED_BODY, hashlib.sha256).hexdigest()

    assert verify_signature(SECRET, SIGNED_BODY, signature)


def test_verify_signature_rejects_tampered_body() -> None:
    import hashlib
    import hmac

    signature = "sha256=" + hmac.new(SECRET.encode(), SIGNED_BODY, hashlib.sha256).hexdigest()

    assert not verify_signature(SECRET, b'{"hello":"attacker"}', signature)


def test_verify_signature_rejects_missing_header() -> None:
    assert not verify_signature(SECRET, SIGNED_BODY, None)


def test_current_sprint_prefers_active() -> None:
    sprints = [{"id": 1, "state": "closed"}, {"id": 2, "state": "active"}, {"id": 3, "state": "future"}]

    assert current_sprint(sprints) == {"id": 2, "state": "active"}
