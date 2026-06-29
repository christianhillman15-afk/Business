"""Backtest the detection + paper strategy on recent historical trades.

Pulls a window of recent trades from the Data API, replays them through a fresh
detector and paper portfolio in chronological order, settles every position
whose market has since resolved, and prints the resulting win rate / ROI.

This estimates the *base* signal edge quickly instead of waiting weeks of live
paper trading. Caveats:
  * It does NOT apply the live smart-money filter (whale quality is a "now"
    stat, so applying it to the past would be lookahead bias).
  * Only markets that have already resolved count toward the win rate; recent
    unresolved positions are reported as still-open.

Run:  python -m whalebot backtest [--config config.yaml]  (set max via env BACKTEST_TRADES)
"""

from __future__ import annotations

import logging
import os

from .client import PolymarketClient
from .config import Config
from .detector import Detector
from .paper import PaperPortfolio

log = logging.getLogger("whalebot.backtest")


def run_backtest(cfg: Config, markets_n: int = 40, trades_per_market: int = 1000) -> dict:
    client = PolymarketClient(
        cfg.polymarket.data_api, cfg.polymarket.gamma_api, cfg.polymarket.clob_api
    )

    # 1. Pull recently-closed, high-volume markets (known outcomes).
    log.info("fetching %d recently-closed markets…", markets_n)
    markets = client.fetch_recent_closed_markets(limit=markets_n)
    if not markets:
        log.warning("no closed markets fetched; cannot backtest")
        return {}

    paper = PaperPortfolio(cfg.paper)
    winners: dict[str, str | None] = {}
    total_trades = 0
    total_signals = 0
    markets_used = 0

    # 2. Replay each market's trades through a fresh detector, then record the
    #    known winner so we can settle exactly.
    for m in markets:
        cid = str(m.get("conditionId", ""))
        if not cid:
            continue
        winner = client.winner_from_market(m)
        if winner is None:
            continue  # 50/50 or unparseable — skip
        winners[cid.lower()] = winner

        trades = []
        offset = 0
        while len(trades) < trades_per_market:
            batch = client.fetch_trades(
                limit=500, taker_only=cfg.poll.taker_only,
                condition_id=cid, offset=offset,
            )
            if not batch:
                break
            trades.extend(batch)
            offset += 500
            if len(batch) < 500:
                break
        if not trades:
            continue
        trades = sorted({t.dedup_key: t for t in trades}.values(), key=lambda t: t.timestamp)
        total_trades += len(trades)
        markets_used += 1

        detector = Detector(cfg.detection, cfg.filters)  # fresh per market
        signals = detector.process(trades, now=trades[-1].timestamp)
        total_signals += len(signals)
        for sig in signals:
            paper.maybe_buy(sig)

    # 3. Settle every position against the known winners.
    paper.settle(lambda c: winners.get(str(c).lower()))

    s = paper.stats()
    log.info(
        "backtest done: %d markets, %d trades, %d signals, %d settled",
        markets_used, total_trades, total_signals, s["settled_trades"],
    )
    return {
        "markets": markets_used,
        "trades": total_trades,
        "signals": total_signals,
        "stats": s,
    }


def print_report(result: dict) -> None:
    if not result:
        print("Backtest produced no data.")
        return
    s = result["stats"]
    print("\n─── Backtest (recently-resolved markets) ───")
    print(f"  Markets replayed: {result['markets']:,}")
    print(f"  Trades replayed:  {result['trades']:,}")
    print(f"  Signals fired:    {result['signals']:,}")
    print(f"  Positions:        {s['open_positions'] + s['settled_trades']:,} "
          f"({s['settled_trades']} settled, {s['open_positions']} still open)")
    print(f"  Win rate:        {s['win_rate'] * 100:.1f}%  ({s['wins']}W / {s['losses']}L)")
    print(f"  Realized PnL:    ${s['realized_pnl']:,.2f}")
    print(f"  Equity:          ${s['equity']:,.2f}  (ROI {s['roi'] * 100:+.1f}%)")
    if s["settled_trades"] < 20:
        print("  ⚠ Few settled trades — pull a longer window for a reliable read.")


def env_markets(default: int = 40) -> int:
    try:
        return int(os.environ.get("BACKTEST_MARKETS", default))
    except (TypeError, ValueError):
        return default
