import re
from datetime import datetime

JIRA_KEY_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b", re.IGNORECASE)


def parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def extract_issue_keys(*texts: str | None) -> set[str]:
    keys: set[str] = set()
    for text in texts:
        if text:
            keys.update(match.upper() for match in JIRA_KEY_PATTERN.findall(text))
    return keys
