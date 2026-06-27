"""Tests for whale-detection logic (no network)."""

from whalebot.config import (
    AccumulationConfig,
    CoordinatedConfig,
    DetectionConfig,
    FiltersConfig,
    WatchlistConfig,
)
from whalebot.detector import Detector
from whalebot.models import Trade


def make_trade(**kw) -> Trade:
    base = dict(
        wallet="0xabc",
        side="BUY",
        asset="tok1",
        condition_id="cond1",
        size=100.0,
        price=0.5,
        timestamp=1_000_000,
        title="Test market",
        slug="test",
        outcome="Yes",
        outcome_index=0,
        tx_hash="0xtx",
    )
    base.update(kw)
    return Trade(**base)


def base_detection(**over) -> DetectionConfig:
    d = DetectionConfig(
        large_trade_usd=5000,
        accumulation=AccumulationConfig(enabled=False),
        coordinated=CoordinatedConfig(enabled=False),
        watchlist=WatchlistConfig(wallets=[], min_usd=500),
    )
    for k, v in over.items():
        setattr(d, k, v)
    return d


def test_large_trade_flagged():
    det = Detector(base_detection(), FiltersConfig(sides=["BUY"]))
    # 20000 shares @ 0.5 = $10k notional -> high severity (>= 2x threshold)
    sigs = det.process([make_trade(size=20000, price=0.5)])
    assert len(sigs) == 1
    assert sigs[0].kind == "large_trade"
    assert sigs[0].severity == "high"
    assert sigs[0].notional_usd == 10000


def test_small_trade_not_flagged():
    det = Detector(base_detection(), FiltersConfig(sides=["BUY"]))
    sigs = det.process([make_trade(size=10, price=0.5)])  # $5
    assert sigs == []


def test_sells_filtered_out():
    det = Detector(base_detection(), FiltersConfig(sides=["BUY"]))
    sigs = det.process([make_trade(side="SELL", size=20000, price=0.5)])
    assert sigs == []


def test_condition_id_filter():
    det = Detector(base_detection(), FiltersConfig(sides=["BUY"], condition_ids=["other"]))
    sigs = det.process([make_trade(size=20000)])
    assert sigs == []


def test_min_price_suppresses_large_trade():
    det = Detector(base_detection(min_price=0.9), FiltersConfig(sides=["BUY"]))
    sigs = det.process([make_trade(size=20000, price=0.5)])  # below min_price
    assert sigs == []


def test_watchlist_alerts_on_small_buy():
    d = base_detection()
    d.watchlist = WatchlistConfig(wallets=["0xwhale"], min_usd=100)
    det = Detector(d, FiltersConfig(sides=["BUY"]))
    sigs = det.process([make_trade(wallet="0xwhale", size=400, price=0.5)])  # $200
    kinds = {s.kind for s in sigs}
    assert "watchlist" in kinds


def test_accumulation_detected_across_trades():
    d = base_detection()
    d.accumulation = AccumulationConfig(
        enabled=True, window_minutes=30, min_total_usd=10000, min_trades=3
    )
    det = Detector(d, FiltersConfig(sides=["BUY"]))
    trades = [
        make_trade(size=8000, price=0.5, timestamp=1000, tx_hash="a"),  # $4k
        make_trade(size=8000, price=0.5, timestamp=1100, tx_hash="b"),  # $4k
        make_trade(size=8000, price=0.5, timestamp=1200, tx_hash="c"),  # $4k -> $12k/3
    ]
    sigs = det.process(trades, now=1300)
    assert any(s.kind == "accumulation" for s in sigs)
    acc = next(s for s in sigs if s.kind == "accumulation")
    assert acc.notional_usd == 12000


def test_coordinated_detected_across_wallets():
    d = base_detection()
    d.coordinated = CoordinatedConfig(
        enabled=True, window_minutes=10, min_wallets=3, min_total_usd=9000
    )
    det = Detector(d, FiltersConfig(sides=["BUY"]))
    trades = [
        make_trade(wallet=f"0x{i}", size=8000, price=0.5, timestamp=1000 + i, tx_hash=str(i))
        for i in range(3)
    ]  # 3 wallets, $12k
    sigs = det.process(trades, now=1100)
    assert any(s.kind == "coordinated" for s in sigs)
