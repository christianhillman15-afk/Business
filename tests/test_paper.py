"""Tests for the paper-trading portfolio (no network)."""

import os
import tempfile

from whalebot.config import PaperConfig
from whalebot.models import Signal
from whalebot.paper import PaperPortfolio


def make_signal(**kw) -> Signal:
    base = dict(
        kind="large_trade",
        severity="high",
        title="Test market",
        outcome="Yes",
        asset="tok1",
        condition_id="cond1",
        notional_usd=10000.0,
        price=0.5,
        message="x",
    )
    base.update(kw)
    return Signal(**base)


def make_cfg(**over) -> PaperConfig:
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    cfg = PaperConfig(
        enabled=True,
        starting_balance=1000,
        stake_usd=50,
        max_position_usd=200,
        ledger_path=path,
        trigger_signals=["large_trade"],
    )
    for k, v in over.items():
        setattr(cfg, k, v)
    return cfg


def test_buy_deducts_cash_and_records_shares():
    pf = PaperPortfolio(make_cfg())
    pos = pf.maybe_buy(make_signal(price=0.5))
    assert pos is not None
    assert pf.cash == 950  # 1000 - 50
    assert pos.shares == 100  # 50 / 0.5
    assert pos.cost_usd == 50


def test_buy_skipped_for_untracked_signal():
    pf = PaperPortfolio(make_cfg())
    assert pf.maybe_buy(make_signal(kind="coordinated")) is None
    assert pf.cash == 1000


def test_buy_skipped_above_max_price():
    pf = PaperPortfolio(make_cfg(max_price=0.9))
    assert pf.maybe_buy(make_signal(price=0.95)) is None


def test_position_exposure_capped():
    pf = PaperPortfolio(make_cfg(stake_usd=150, max_position_usd=200))
    pf.maybe_buy(make_signal(price=0.5))  # stakes 150
    pos = pf.maybe_buy(make_signal(price=0.5))  # only 50 room left
    assert pos is not None
    assert pos.cost_usd == 200  # 150 + 50
    pf.maybe_buy(make_signal(price=0.5))  # no room -> no change
    assert pos.cost_usd == 200


def test_settlement_win_pays_out():
    pf = PaperPortfolio(make_cfg())
    pf.maybe_buy(make_signal(price=0.5))  # 100 shares, cash 950
    pf.settle(resolver=lambda cid: "Yes")  # our outcome won
    s = pf.stats()
    assert s["wins"] == 1
    assert s["losses"] == 0
    assert s["win_rate"] == 1.0
    # payout = 100 shares * $1 = 100; cash 950 + 100 = 1050
    assert pf.cash == 1050
    assert s["realized_pnl"] == 50  # 100 payout - 50 cost


def test_settlement_loss():
    pf = PaperPortfolio(make_cfg())
    pf.maybe_buy(make_signal(price=0.5))
    pf.settle(resolver=lambda cid: "No")  # other outcome won
    s = pf.stats()
    assert s["losses"] == 1
    assert s["win_rate"] == 0.0
    assert pf.cash == 950  # no payout
    assert s["realized_pnl"] == -50


def test_unresolved_market_not_settled():
    pf = PaperPortfolio(make_cfg())
    pf.maybe_buy(make_signal(price=0.5))
    settled = pf.settle(resolver=lambda cid: None)
    assert settled == []
    assert pf.stats()["settled_trades"] == 0


def test_roundtrip_serialisation():
    cfg = make_cfg()
    pf = PaperPortfolio(cfg)
    pf.maybe_buy(make_signal(price=0.5))
    blob = pf.to_blob()
    pf2 = PaperPortfolio(cfg, blob)
    assert pf2.cash == pf.cash
    assert len(pf2.positions) == 1
