"""Configuration loading and validation.

Config lives in a YAML file; secrets are read from environment variables (and an
optional ``.env`` file). The dataclasses below give us a typed, validated view of
the config so the rest of the code never touches raw dicts.
"""

from __future__ import annotations

import os
from dataclasses import MISSING, dataclass, field, fields
from typing import Any

import yaml


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge ``override`` into ``base`` (returns a new dict)."""
    out = dict(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


@dataclass
class PolymarketConfig:
    data_api: str = "https://data-api.polymarket.com"
    gamma_api: str = "https://gamma-api.polymarket.com"
    clob_api: str = "https://clob.polymarket.com"


@dataclass
class PollConfig:
    interval_seconds: float = 15.0
    trades_per_poll: int = 500
    taker_only: bool = True


@dataclass
class FiltersConfig:
    condition_ids: list[str] = field(default_factory=list)
    sides: list[str] = field(default_factory=lambda: ["BUY"])


@dataclass
class AccumulationConfig:
    enabled: bool = True
    window_minutes: float = 30.0
    min_total_usd: float = 10_000.0
    min_trades: int = 3


@dataclass
class CoordinatedConfig:
    enabled: bool = True
    window_minutes: float = 10.0
    min_wallets: int = 4
    min_total_usd: float = 15_000.0


@dataclass
class WatchlistConfig:
    wallets: list[str] = field(default_factory=list)
    min_usd: float = 500.0


@dataclass
class DetectionConfig:
    large_trade_usd: float = 5_000.0
    min_price: float = 0.0  # ignore aggressive buys below this price (0 = off)
    # suppress repeat alerts for the same (market, outcome, signal) within this
    # many minutes, to cut noise (0 = off)
    alert_cooldown_minutes: float = 10.0
    accumulation: AccumulationConfig = field(default_factory=AccumulationConfig)
    coordinated: CoordinatedConfig = field(default_factory=CoordinatedConfig)
    watchlist: WatchlistConfig = field(default_factory=WatchlistConfig)


@dataclass
class FileNotifyConfig:
    enabled: bool = True
    path: str = "./alerts.jsonl"


@dataclass
class WebhookNotifyConfig:
    enabled: bool = False
    url_env: str = "WHALEBOT_WEBHOOK_URL"


@dataclass
class TelegramNotifyConfig:
    enabled: bool = False
    bot_token_env: str = "TELEGRAM_BOT_TOKEN"
    chat_id: str = ""


@dataclass
class DailySummaryConfig:
    enabled: bool = True
    hour_utc: int = 13  # send the daily recap around this UTC hour


@dataclass
class NotificationsConfig:
    console: bool = True
    file: FileNotifyConfig = field(default_factory=FileNotifyConfig)
    webhook: WebhookNotifyConfig = field(default_factory=WebhookNotifyConfig)
    telegram: TelegramNotifyConfig = field(default_factory=TelegramNotifyConfig)
    daily_summary: DailySummaryConfig = field(default_factory=DailySummaryConfig)


@dataclass
class SizingConfig:
    mode: str = "fixed"  # "fixed" | "percent"
    fixed_usd: float = 50.0
    percent_of_whale: float = 1.0
    max_usd: float = 200.0


@dataclass
class FollowConfig:
    enabled: bool = False
    dry_run: bool = True
    trigger_signals: list[str] = field(
        default_factory=lambda: ["large_trade", "accumulation", "watchlist"]
    )
    sizing: SizingConfig = field(default_factory=SizingConfig)
    max_price: float = 0.95
    order_type: str = "GTC"  # "GTC" | "FOK"
    daily_max_usd: float = 1_000.0
    # Secrets are read from env, never the YAML file:
    private_key_env: str = "POLYMARKET_PRIVATE_KEY"
    funder_env: str = "POLYMARKET_FUNDER"  # proxy/funder address (optional)
    chain_id: int = 137


@dataclass
class FillModelConfig:
    """Make paper fills realistic: you never trade at the mid price.

    A buy crosses the spread (fills a bit above the quoted price) and a
    sell/valuation fills a bit below, plus an optional fee. This keeps the paper
    win rate honest so it's safe to base a real-money decision on.
    """

    enabled: bool = True
    spread_bps: float = 100.0  # half-spread each way; 100 bps = 1% (≈2% round trip)
    fee_bps: float = 0.0  # Polymarket trading fee (currently ~0)


@dataclass
class SmartMoneyConfig:
    """Only follow whales with a track record, and don't chase price.

    Whale quality (all-time PnL / win rate) comes from Polymarket and is cached.
    If a whale's stats can't be fetched, we fail OPEN (allow the trade) so a
    transient API hiccup never silently halts all trading.
    """

    enabled: bool = True
    min_all_time_pnl: float = 0.0  # whale must be net up at least this much
    min_win_rate: float = 0.0  # 0 = ignore (their win rate is approximate)
    max_chase_slippage: float = 0.06  # skip if price already ran >6% past entry
    cache_ttl_minutes: float = 360.0


@dataclass
class PaperConfig:
    """Paper-trading ('demo account') settings.

    When a tracked signal fires, the bot simulates buying the flagged outcome
    with fake money, records it to a ledger, and later settles it against the
    real market resolution to compute a running win rate.
    """

    enabled: bool = True
    starting_balance: float = 1_000.0
    stake_usd: float = 50.0  # fake dollars per flagged trade
    max_position_usd: float = 200.0  # cap exposure per (market, outcome)
    trigger_signals: list[str] = field(
        default_factory=lambda: ["large_trade", "accumulation", "coordinated", "watchlist"]
    )
    ledger_path: str = "./paper_ledger.jsonl"
    settle_interval_minutes: float = 30.0
    # don't paper-buy above this price (avoid chasing near-certain outcomes)
    max_price: float = 0.97
    # directory the dashboard drops manual buy/sell commands into; the bot
    # consumes them each tick (single-writer: only the bot mutates the book).
    commands_dir: str = "./paper_commands"
    smart_money: SmartMoneyConfig = field(default_factory=SmartMoneyConfig)
    fills: FillModelConfig = field(default_factory=FillModelConfig)


@dataclass
class DashboardConfig:
    """Web dashboard settings.

    Serves a simple browser page (and a JSON API) showing the paper account,
    open positions, and recent whale alerts. No extra dependencies — uses the
    Python standard library only.
    """

    host: str = "0.0.0.0"  # 0.0.0.0 = reachable from your browser over the internet
    port: int = 8080
    # Optional access token. If set, the page requires ?token=... in the URL so
    # random visitors can't view it. Empty = no token (fine; only fake-money data).
    token: str = ""
    recent_alerts: int = 50
    refresh_seconds: int = 15


@dataclass
class StateConfig:
    path: str = "./whalebot_state.json"
    dedup_ttl_minutes: float = 120.0


@dataclass
class Config:
    polymarket: PolymarketConfig = field(default_factory=PolymarketConfig)
    poll: PollConfig = field(default_factory=PollConfig)
    filters: FiltersConfig = field(default_factory=FiltersConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    follow: FollowConfig = field(default_factory=FollowConfig)
    paper: PaperConfig = field(default_factory=PaperConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    state: StateConfig = field(default_factory=StateConfig)
    log_level: str = "INFO"


def _build(cls, data: Any):
    """Instantiate a (possibly nested) dataclass from a plain dict.

    Unknown keys are ignored so configs stay forward-compatible; nested
    dataclass fields are constructed recursively.
    """
    if not isinstance(data, dict):
        return data
    kwargs = {}
    type_hints = {f.name: f.type for f in fields(cls)}
    valid = set(type_hints)
    for key, value in data.items():
        if key not in valid:
            continue
        f = next(fl for fl in fields(cls) if fl.name == key)
        if f.default_factory is not MISSING:  # type: ignore[misc]
            default = f.default_factory()  # type: ignore[misc]
        else:
            default = f.default
        if hasattr(default, "__dataclass_fields__") and isinstance(value, dict):
            kwargs[key] = _build(type(default), value)
        else:
            kwargs[key] = value
    return cls(**kwargs)


def load_config(path: str) -> Config:
    """Load and validate config from a YAML file.

    ``log_level`` may also come from the top-level YAML key ``logging.level``.
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    if not isinstance(raw, dict):
        raise ValueError(f"Config root must be a mapping, got {type(raw).__name__}")

    # Accept either top-level `log_level` or `logging: {level: ...}`.
    if "logging" in raw and isinstance(raw["logging"], dict):
        raw.setdefault("log_level", raw["logging"].get("level", "INFO"))

    cfg = _build(Config, raw)
    _validate(cfg)
    return cfg


def _validate(cfg: Config) -> None:
    errors: list[str] = []

    if cfg.poll.interval_seconds <= 0:
        errors.append("poll.interval_seconds must be > 0")
    if cfg.poll.trades_per_poll <= 0:
        errors.append("poll.trades_per_poll must be > 0")
    if cfg.detection.large_trade_usd < 0:
        errors.append("detection.large_trade_usd must be >= 0")
    if not (0.0 <= cfg.detection.min_price <= 1.0):
        errors.append("detection.min_price must be within [0, 1]")
    if cfg.follow.sizing.mode not in ("fixed", "percent"):
        errors.append("follow.sizing.mode must be 'fixed' or 'percent'")
    if cfg.follow.order_type not in ("GTC", "FOK"):
        errors.append("follow.order_type must be 'GTC' or 'FOK'")
    if not (0.0 < cfg.follow.max_price <= 1.0):
        errors.append("follow.max_price must be within (0, 1]")
    if cfg.paper.starting_balance <= 0:
        errors.append("paper.starting_balance must be > 0")
    if cfg.paper.stake_usd <= 0:
        errors.append("paper.stake_usd must be > 0")
    if not (0.0 < cfg.paper.max_price <= 1.0):
        errors.append("paper.max_price must be within (0, 1]")

    valid_sides = {"BUY", "SELL"}
    cfg.filters.sides = [s.upper() for s in cfg.filters.sides]
    if any(s not in valid_sides for s in cfg.filters.sides):
        errors.append("filters.sides may only contain BUY/SELL")

    # Normalise watchlist + condition filters to lowercase for matching.
    cfg.detection.watchlist.wallets = [w.lower() for w in cfg.detection.watchlist.wallets]
    cfg.filters.condition_ids = [c.lower() for c in cfg.filters.condition_ids]

    if errors:
        raise ValueError("Invalid config:\n  - " + "\n  - ".join(errors))


def env(name: str, default: str | None = None) -> str | None:
    """Read an environment variable (thin wrapper for testability)."""
    return os.environ.get(name, default)
