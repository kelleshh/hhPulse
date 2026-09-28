from __future__ import annotations


def api_headers(*, access_token: str, user_agent: str) -> dict[str, str]:
    token = access_token.strip()
    agent = user_agent.strip()
    if not agent:
        raise ValueError("HH API user agent must not be empty")
    headers = {
        "Accept": "application/json",
        "HH-User-Agent": agent,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
