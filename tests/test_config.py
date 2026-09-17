from hhpulse.config import Settings


def test_settings_from_env_uses_dataclass_defaults(monkeypatch) -> None:
    for name in ("HHPULSE_DB_PATH", "HHPULSE_HOST", "HHPULSE_PORT", "HHPULSE_LOG_LEVEL"):
        monkeypatch.delenv(name, raising=False)

    assert Settings.from_env() == Settings()
