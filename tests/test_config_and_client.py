"""Tests for config loading/validation, state, and client parsing (no network)."""

import os
import tempfile

import pytest

from whalebot.client import _parse_json_list
from whalebot.config import load_config
from whalebot.state import State


def write_cfg(text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
    return path


def test_defaults_when_minimal_config():
    path = write_cfg("paper:\n  starting_balance: 500\n")
    cfg = load_config(path)
    assert cfg.paper.starting_balance == 500
    assert cfg.detection.large_trade_usd == 5000  # default preserved
    assert cfg.poll.interval_seconds == 15


def test_nested_override_and_logging_alias():
    path = write_cfg(
        "detection:\n"
        "  large_trade_usd: 12345\n"
        "  accumulation:\n"
        "    min_trades: 7\n"
        "logging:\n"
        "  level: DEBUG\n"
    )
    cfg = load_config(path)
    assert cfg.detection.large_trade_usd == 12345
    assert cfg.detection.accumulation.min_trades == 7
    assert cfg.detection.accumulation.window_minutes == 30  # default kept
    assert cfg.log_level == "DEBUG"


def test_validation_rejects_bad_values():
    path = write_cfg("poll:\n  interval_seconds: -1\n")
    with pytest.raises(ValueError):
        load_config(path)


def test_watchlist_and_conditions_lowercased():
    path = write_cfg(
        "detection:\n"
        "  watchlist:\n"
        "    wallets: ['0xABCDEF']\n"
        "filters:\n"
        "  condition_ids: ['0xDEADBEEF']\n"
    )
    cfg = load_config(path)
    assert cfg.detection.watchlist.wallets == ["0xabcdef"]
    assert cfg.filters.condition_ids == ["0xdeadbeef"]


def test_state_dedup_and_prune():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    st = State(path, dedup_ttl_minutes=1)
    assert st.is_new("k1")
    st.mark_seen("k1", ts=1000)
    assert not st.is_new("k1")
    # prune everything older than now-60s; with now=2000 the entry at 1000 is stale
    removed = st.prune(now=2000)
    assert removed == 1
    assert st.is_new("k1")


def test_state_persistence_roundtrip():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    st = State(path)
    st.mark_seen("x", ts=123)
    st.add_follow_spend("2026-01-01", 50)
    st.paper = {"cash": 999}
    st.save()

    st2 = State(path)
    assert not st2.is_new("x")
    assert st2.follow_spent_today("2026-01-01") == 50
    assert st2.paper == {"cash": 999}


@pytest.mark.parametrize(
    "value,expected",
    [
        ('["Yes", "No"]', ["Yes", "No"]),
        (["Yes", "No"], ["Yes", "No"]),
        ("not-json", []),
        (None, []),
        ("[1, 2]", [1, 2]),
    ],
)
def test_parse_json_list(value, expected):
    assert _parse_json_list(value) == expected
