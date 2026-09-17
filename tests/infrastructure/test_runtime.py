from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from hhpulse.infrastructure.runtime import FileHtmlQuarantine


async def test_quarantine_saves_private_bounded_file_and_purges_it(tmp_path) -> None:
    now = datetime(2026, 9, 17, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    quarantine = FileHtmlQuarantine(
        tmp_path,
        retention=timedelta(hours=24),
        max_document_bytes=8,
    )

    reference = await quarantine.save(
        run_id="run/unsafe",
        unit_id="unit/unsafe",
        html="0123456789",
        observed_at=now,
    )

    path = tmp_path / reference
    assert path.read_bytes() == b"01234567"
    assert path.stat().st_mode & 0o777 == 0o600
    removed = await quarantine.purge_expired(now=now + timedelta(hours=25))
    assert removed == 1
    assert not path.exists()
