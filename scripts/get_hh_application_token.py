#!/usr/bin/env python3
"""Generate an HH application token once from client_id/client_secret."""

from __future__ import annotations

import argparse
import json
import sys

import requests


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--client-id", required=True)
    p.add_argument("--client-secret", required=True)
    p.add_argument("--contact", required=True)
    a = p.parse_args()
    r = requests.post(
        "https://api.hh.ru/token",
        headers={"HH-User-Agent": f"hhPulse-token-bootstrap/0.1 ({a.contact})"},
        data={
            "grant_type": "client_credentials",
            "client_id": a.client_id,
            "client_secret": a.client_secret,
        },
        timeout=(10, 30),
    )
    if r.status_code != 200:
        print(f"HTTP {r.status_code}: {r.text}", file=sys.stderr)
        return 1
    payload = r.json()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(
        "\nСохраните access_token в HHPULSE_HH_ACCESS_TOKEN. "
        "Не запускайте генерацию повторно без причины."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
