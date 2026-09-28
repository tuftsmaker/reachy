#!/usr/bin/env python3
"""Thin Calendly API v2 client -- stdlib only.

Covers what the robot demos need:
  - current user + event types
  - available times for an event type
  - creating a booking (Scheduling API; requires a paid Calendly plan)
  - single-use scheduling links (works on any plan)
  - upcoming scheduled events + cancellation

Token: `CALENDLY_TOKEN` env var, or ~/.config/tuftsmaker/calendly_key
(one-time setup: printf '%s' 'TOKEN' > ~/.config/tuftsmaker/calendly_key)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://api.calendly.com"
TOKEN_FILE = Path.home() / ".config/tuftsmaker/calendly_key"


def token() -> str:
    value = os.environ.get("CALENDLY_TOKEN", "").strip()
    if value:
        return value
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    raise RuntimeError(
        "No Calendly token. Create one at https://calendly.com/integrations/api_webhooks "
        f"and save it to {TOKEN_FILE} (chmod 600)."
    )


def _request(method: str, path: str, params: dict | None = None, body: dict | None = None) -> dict:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token()}",
            "Content-Type": "application/json",
            # Calendly's edge (Cloudflare) blocks the default python-urllib
            # signature with error 1010; identify the app instead.
            "User-Agent": "reachy-mini-demo/1.0 (+https://github.com/tuftsmaker/reachy)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        raise RuntimeError(f"Calendly HTTP {e.code} on {method} {path}: {detail}") from e


# ----------------------------------------------------------------- basics


def me() -> dict:
    return _request("GET", "/users/me")["resource"]


def event_types(user_uri: str) -> list[dict]:
    return _request("GET", "/event_types", {"user": user_uri, "active": "true"})["collection"]


def find_event_type(name_part: str) -> dict:
    """Case-insensitive substring match over the user's active event types."""
    user = me()
    matches = [e for e in event_types(user["uri"]) if name_part.lower() in e["name"].lower()]
    if not matches:
        raise RuntimeError(f"No event type matching {name_part!r}")
    if len(matches) > 1:
        names = ", ".join(e["name"] for e in matches)
        raise RuntimeError(f"{len(matches)} event types match {name_part!r}: {names}")
    return matches[0]


# ----------------------------------------------------------------- scheduling


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def available_times(event_type_uri: str, days: int = 7) -> list[dict]:
    # A small buffer avoids "start_time must be in the future" from clock skew.
    start = datetime.now(timezone.utc) + timedelta(minutes=10)
    end = start + timedelta(days=days)
    data = _request(
        "GET",
        "/event_type_available_times",
        {
            "event_type": event_type_uri,
            "start_time": _rfc3339(start),
            "end_time": _rfc3339(end),
        },
    )
    return [s for s in data["collection"] if s.get("status") == "available"]


def location_kind(event_type_uri: str) -> str | None:
    """The first location kind configured on an event type (e.g. zoom_conference)."""
    uuid = event_type_uri.rstrip("/").split("/")[-1]
    detail = _request("GET", f"/event_types/{uuid}")["resource"]
    locations = detail.get("locations") or []
    return locations[0]["kind"] if locations else None


def book(
    event_type_uri: str,
    start_time: str,
    name: str,
    email: str,
    tz: str = "America/New_York",
    location_kind: str | None = None,
) -> dict:
    """Create a real booking (Scheduling API; requires a paid plan)."""
    body: dict = {
        "event_type": event_type_uri,
        "start_time": start_time,
        "invitee": {"name": name, "email": email, "timezone": tz},
    }
    if location_kind:
        body["location"] = {"kind": location_kind}
    data = _request("POST", "/invitees", body=body)
    return data["resource"]


def single_use_link(event_type_uri: str) -> str:
    """A one-off booking URL (works without the paid Scheduling API)."""
    data = _request(
        "POST", "/scheduling_links",
        body={"max_event_count": 1, "owner": event_type_uri, "owner_type": "EventType"},
    )
    return data["resource"]["booking_url"]


def upcoming(user_uri: str, days: int = 30) -> list[dict]:
    now = datetime.now(timezone.utc)
    data = _request(
        "GET",
        "/scheduled_events",
        {
            "user": user_uri,
            "min_start_time": _rfc3339(now),
            "max_start_time": _rfc3339(now + timedelta(days=days)),
            "status": "active",
            "sort": "start_time:asc",
        },
    )
    return data["collection"]


def cancel(event_uri: str, reason: str = "Cancelled via demo") -> None:
    uuid = event_uri.rstrip("/").split("/")[-1]
    _request("POST", f"/scheduled_events/{uuid}/cancellation", body={"reason": reason})


def pretty(slot_iso: str, tz: str = "America/New_York") -> str:
    """Human-readable local time for a slot."""
    from zoneinfo import ZoneInfo

    dt = datetime.fromisoformat(slot_iso.replace("Z", "+00:00")).astimezone(ZoneInfo(tz))
    return dt.strftime("%a %b %d, %-I:%M %p %Z")
