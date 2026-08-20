import html
import re
from datetime import timedelta
from html.parser import HTMLParser

RESOURCE_RE = re.compile(
    r"teams(?:\('([^']+)'\)|/([^/]+))/channels(?:\('([^']+)'\)|/([^/]+))/messages(?:\('([^']+)'\)|/([^/]+))"
)


def subscription_expiration(now):
    return (now + timedelta(minutes=55)).isoformat().replace("+00:00", "Z")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def text_content(value: str) -> str:
    parser = _Text()
    parser.feed(value or "")
    return " ".join(" ".join(parser.parts).split())


def safe_html(value: str) -> str:
    return html.escape(text_content(value))


def parse_resource(resource: str):
    match = RESOURCE_RE.search(resource or "")
    if not match:
        raise ValueError("Unsupported Graph notification resource")
    team_id, team_alt, channel_id, channel_alt, message_id, message_alt = match.groups()
    return team_id or team_alt, channel_id or channel_alt, message_id or message_alt


def ticket_subject(message: dict) -> str:
    value = text_content(message.get("subject") or message.get("body", {}).get("content", ""))
    return (value[:117] + "...") if len(value) > 120 else (value or "Teams support request")
