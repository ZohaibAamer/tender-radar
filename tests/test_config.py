from datetime import date

from tender_radar import config


def test_today_respects_pinned_env(monkeypatch):
    monkeypatch.setenv("TENDER_RADAR_TODAY", "2026-10-15")
    assert config.today() == date(2026, 10, 15)


def test_today_defaults_to_wall_clock(monkeypatch):
    monkeypatch.delenv("TENDER_RADAR_TODAY", raising=False)
    assert config.today() == date.today()
