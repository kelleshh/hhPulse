#!/usr/bin/env python3
"""Conservative one-page probe for the public HH resume search.

Purpose: verify whether the public HTML page still exposes the aggregate "found"
resume count for the same filters hhPulse used before the API migration.

This script deliberately does NOT attempt to bypass CAPTCHA/WAF/login controls:
- one stable descriptive User-Agent;
- deterministic delay between multiple roles;
- no proxy rotation, browser fingerprint spoofing, cookie farming, or CAPTCHA solving;
- HTTP 403/429 or block-page markers stop the run immediately.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path

import requests

SEARCH_URL = "https://hh.ru/search/resume"
COUNT_RE = re.compile(r"Найден[оа]?\s+([\d\s\u00a0\u202f]+)\s+резюм", re.IGNORECASE)
BLOCK_MARKERS = (
    "captcha",
    "капча",
    "access denied",
    "доступ ограничен",
    "слишком много запросов",
    "too many requests",
    "web application firewall",
)


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "template"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "template"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0:
            self.parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


@dataclass(frozen=True, slots=True)
class ProbeResult:
    role_id: str
    found: int
    url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Проверить публичный счётчик резюме HH без обхода CAPTCHA/WAF."
    )
    parser.add_argument(
        "--role", action="append", required=True, help="ID professional_role. Можно повторять."
    )
    parser.add_argument("--area", default="1", help="HH area id, по умолчанию 1 (Москва).")
    parser.add_argument(
        "--days", type=int, default=60, help="Окно публикации резюме, по умолчанию 60 дней."
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Пауза между разными ролями. Минимум 3 секунды.",
    )
    parser.add_argument(
        "--contact",
        required=True,
        help="Контактная почта для честного User-Agent, например you@example.com.",
    )
    parser.add_argument(
        "--diagnostics-dir",
        default="./hh_resume_probe_diagnostics",
        help="Куда сохранить неожиданный/заблокированный HTML для диагностики.",
    )
    return parser.parse_args()


def build_params(*, role_id: str, area: str, days: int) -> list[tuple[str, str]]:
    if days < 1:
        raise ValueError("days must be positive")
    today = date.today()
    date_from = today - timedelta(days=days - 1)
    # These match the old hhPulse HTML methodology as closely as possible.
    return [
        ("logic", "normal"),
        ("pos", "full_text"),
        ("exp_period", "all_time"),
        ("filter_exp_period", "all_time"),
        ("area", area),
        ("relocation", "living_or_relocation"),
        ("job_search_status", "active_search"),
        ("job_search_status", "looking_for_offers"),
        ("job_search_status", "unknown"),
        ("gender", "unknown"),
        ("order_by", "relevance"),
        ("search_period", "-1"),
        ("date_from", date_from.strftime("%d.%m.%Y")),
        ("date_to", today.strftime("%d.%m.%Y")),
        ("items_on_page", "20"),
        ("no_magic", "true"),
        ("hhtmFrom", "resume_search_form"),
        ("L_save_area", "true"),
        ("text", ""),
        ("professional_role", role_id),
    ]


def visible_text(raw_html: str) -> str:
    parser = VisibleTextParser()
    parser.feed(raw_html)
    parser.close()
    return html.unescape(parser.text())


def parse_found(raw_html: str) -> int:
    text = visible_text(raw_html)
    match = COUNT_RE.search(text)
    if not match:
        lowered = text.casefold()
        if "по запросу ничего не найдено" in lowered or "ничего не найдено" in lowered:
            return 0
        raise ValueError("не найден видимый счётчик вида 'Найдено N резюме'")
    digits = re.sub(r"\D", "", match.group(1))
    if not digits:
        raise ValueError("счётчик найден, но число не распознано")
    return int(digits)


def block_reason(response: requests.Response) -> str | None:
    if response.status_code in {403, 429}:
        return f"HTTP {response.status_code}"
    prefix = response.text[:300_000].casefold()
    for marker in BLOCK_MARKERS:
        if marker in prefix:
            return f"block marker: {marker}"
    return None


def save_diagnostic(directory: Path, *, role_id: str, response: requests.Response) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%dT%H%M%S")
    path = directory / f"resume_probe_{role_id}_{timestamp}_{response.status_code}.html"
    path.write_text(response.text, encoding=response.encoding or "utf-8", errors="replace")
    return path


def run_probe(
    session: requests.Session,
    *,
    role_id: str,
    area: str,
    days: int,
    diagnostics_dir: Path,
) -> ProbeResult:
    response = session.get(
        SEARCH_URL,
        params=build_params(role_id=role_id, area=area, days=days),
        timeout=(10, 30),
        allow_redirects=True,
    )
    reason = block_reason(response)
    if reason is not None:
        diagnostic = save_diagnostic(diagnostics_dir, role_id=role_id, response=response)
        raise RuntimeError(
            f"HH остановил запрос ({reason}). Диагностика: {diagnostic}. "
            "Скрипт намеренно не пытается обходить защиту."
        )
    if response.status_code != 200:
        diagnostic = save_diagnostic(diagnostics_dir, role_id=role_id, response=response)
        raise RuntimeError(f"неожиданный HTTP {response.status_code}; диагностика: {diagnostic}")
    try:
        found = parse_found(response.text)
    except ValueError as exc:
        diagnostic = save_diagnostic(diagnostics_dir, role_id=role_id, response=response)
        raise RuntimeError(f"{exc}; диагностика: {diagnostic}") from exc
    return ProbeResult(role_id=role_id, found=found, url=response.url)


def main() -> int:
    args = parse_args()
    interval = max(3.0, args.interval)
    diagnostics_dir = Path(args.diagnostics_dir)
    roles = tuple(dict.fromkeys(role.strip() for role in args.role if role.strip()))
    if not roles:
        print("Нет непустых --role", file=sys.stderr)
        return 2

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": f"hhPulse-resume-count-probe/0.1 ({args.contact})",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ru-RU,ru;q=0.9",
        }
    )

    try:
        for index, role_id in enumerate(roles):
            if index:
                time.sleep(interval)
            result = run_probe(
                session,
                role_id=role_id,
                area=args.area,
                days=args.days,
                diagnostics_dir=diagnostics_dir,
            )
            print(
                json.dumps(
                    {"role_id": result.role_id, "found": result.found, "url": result.url},
                    ensure_ascii=False,
                )
            )
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
