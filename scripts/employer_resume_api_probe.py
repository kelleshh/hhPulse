#!/usr/bin/env python3
"""Read-only probe for employer resume-search access in the official HH API.

It does not purchase anything and does not open individual resumes. It checks /me,
manager method access, daily resume-view limits, and finally GET /resumes?per_page=1.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import requests

BASE = "https://api.hh.ru"


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default=os.getenv("HHPULSE_HH_EMPLOYER_TOKEN", ""))
    parser.add_argument("--contact", required=True)
    parser.add_argument("--area", default="1")
    parser.add_argument("--role", required=True)
    parser.add_argument("--period", type=int, default=60)
    return parser.parse_args()


def get_json(session: requests.Session, path: str, *, params: Any = None) -> tuple[int, Any]:
    response = session.get(f"{BASE}{path}", params=params, timeout=(10, 30))
    try:
        payload: Any = response.json()
    except ValueError:
        payload = {"raw": response.text[:1000]}
    return response.status_code, payload


def main() -> int:
    cfg = args()
    if not cfg.token.strip():
        print(
            "Нужен user OAuth token работодателя: --token или HHPULSE_HH_EMPLOYER_TOKEN",
            file=sys.stderr,
        )
        return 2
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {cfg.token.strip()}",
            "HH-User-Agent": f"hhPulse-employer-access-probe/0.1 ({cfg.contact})",
            "Accept": "application/json",
        }
    )
    try:
        status, me = get_json(session, "/me")
        print(
            json.dumps(
                {"step": "me", "status": status, "payload": me}, ensure_ascii=False, indent=2
            )
        )
        if status != 200 or not isinstance(me, dict) or not me.get("is_employer"):
            print("Токен не принадлежит работодателю или /me недоступен.", file=sys.stderr)
            return 1

        employer = me.get("employer") or {}
        manager = me.get("manager") or {}
        employer_id = str(employer.get("id") or "").strip()
        manager_id = str(manager.get("id") or me.get("id") or "").strip()
        if employer_id and manager_id:
            status, access = get_json(
                session,
                f"/employers/{employer_id}/managers/{manager_id}/method_access",
            )
            print(
                json.dumps(
                    {"step": "method_access", "status": status, "payload": access},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            status, limits = get_json(
                session,
                f"/employers/{employer_id}/managers/{manager_id}/limits/resume",
            )
            print(
                json.dumps(
                    {"step": "resume_limits", "status": status, "payload": limits},
                    ensure_ascii=False,
                    indent=2,
                )
            )

        status, resumes = get_json(
            session,
            "/resumes",
            params=[
                ("area", cfg.area),
                ("professional_role", cfg.role),
                ("period", str(cfg.period)),
                ("relocation", "living_or_relocation"),
                ("job_search_status", "active_search"),
                ("job_search_status", "looking_for_offers"),
                ("order_by", "publication_time"),
                ("per_page", "1"),
            ],
        )
        summary = resumes
        if status == 200 and isinstance(resumes, dict):
            summary = {
                "found": resumes.get("found"),
                "page": resumes.get("page"),
                "pages": resumes.get("pages"),
                "per_page": resumes.get("per_page"),
            }
        print(
            json.dumps(
                {"step": "resume_search", "status": status, "payload": summary},
                ensure_ascii=False,
                indent=2,
            )
        )
        if status == 200:
            print("RESULT: официальный поиск резюме API доступен этому employer token.")
            return 0
        if status == 403:
            print(
                "RESULT: этому аккаунту/приложению официальный поиск резюме API не разрешён. "
                "Ничего не покупалось."
            )
            return 3
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
