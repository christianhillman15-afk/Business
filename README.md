# 🐋 Polymarket Whale Bot

A config-driven daemon that watches **Polymarket** trade flow, flags suspicious
buying that looks like a whale is about to push a price, alerts you, and tracks
how well those signals perform using a **fake-money paper account** — so you can
measure a real win rate *before* risking a cent.

It can also (optionally) **follow** the whale by placing real orders, but that's
off by default and double-gated behind a dry-run flag and spend caps.

---

## What it does

1. **Polls** the Polymarket Data API trade feed every few seconds.
2. **Detects** suspicious activity with several configurable signals:
   - **Large single buy** — one trade above a USDC threshold (default $5,000).
   - **Accumulation** — one wallet quietly stacking a position over a time window.
   - **Coordinated buying** — many wallets piling into the same outcome fast.
   - **Watchlist** — always alert on wallets you flag as known whales.
3. **Alerts** you via console, a JSONL file, a Discord/Slack webhook, or Telegram.
4. **Paper-trades** every flagged signal with fake money (default $1,000 bankroll),
   logs it to a ledger, then **settles** each position against the real market
   resolution to compute a running **win rate / PnL**.
5. **Optionally follows** the trade with real orders (off by default).

---

## Quick start

```bash
# 1. Install core dependencies (no blockchain libs needed for detection/paper).
pip install -r requirements.txt

# 2. Create your config.
cp config.example.yaml config.yaml      # then edit thresholds to taste

# 3. (Optional) set up secrets for webhook/telegram/live trading.
cp .env.example .env                     # then fill in

# 4. Smoke-test a single poll cycle.
python -m whalebot test

# 5. Run the daemon.
python -m whalebot run
```

### Commands

| Command | What it does |
|---------|--------------|
| `python -m whalebot run`    | Start the polling daemon (default). |
| `python -m whalebot test`   | Run one poll cycle and print the paper account, then exit. |
| `python -m whalebot report` | Print current paper-account win rate / PnL and exit. |
| `python -m whalebot settle` | Force a settlement pass against market resolutions. |

All commands accept `-c / --config <path>` (defaults to `config.yaml`).

---

## The paper account (win-rate tracking)

This is the heart of the "prove it works first" workflow you asked for:

- Starts with **$1,000 of fake money** (`paper.starting_balance`).
- When a signal fires, it simulates **buying** the flagged outcome at the trade's
  price, staking `paper.stake_usd` (default $50), capped per market by
  `paper.max_position_usd`.
- Every action is appended to **`paper_ledger.jsonl`** (open / add / settle).
- On a schedule (`paper.settle_interval_minutes`), open positions whose markets
  have **resolved** are settled from the real Gamma API:
  - bought outcome **won** → each share pays out **$1**
  - bought outcome **lost** → position is worth **$0**
- `python -m whalebot report` shows:

```
─── Paper account ───
  Starting:   $1,000.00
  Cash:       $640.00
  Open:       4 positions ($200.00 cost)
  Equity:     $1,085.00  (ROI +8.5%)
  Settled:    12  →  8W / 4L
  Win rate:   66.7%
  Realized PnL: $245.00
```

Let it run for a while, watch the win rate stabilize, and only *then* consider
turning on live following.

---

## Going live (optional, advanced)

Live following is **off** (`follow.enabled: false`) and **dry-run** by default.
When `follow.enabled: true` and `follow.dry_run: true`, the bot logs the exact
order it *would* place without sending it — a safe middle step.

To place real orders:

```bash
pip install py-clob-client        # heavy: pulls in web3 etc.
```

Set in `.env`:

```
POLYMARKET_PRIVATE_KEY=0x...      # wallet holding your USDC on Polygon
POLYMARKET_FUNDER=0x...           # your Polymarket proxy address (from your profile)
```

Then in `config.yaml` set `follow.enabled: true` and `follow.dry_run: false`.
Safety rails always apply: `follow.max_price`, `follow.sizing.max_usd`, and a
hard per-day `follow.daily_max_usd` cap.

> ⚠️ Real money is at risk. Prediction-market signals are noisy and "whale"
> activity can be wrong, manipulative, or already priced in. Start with paper
> trading, use small caps, and never risk more than you can lose.

---

## Configuration

Everything is driven by `config.yaml` — see **`config.example.yaml`** for the
full annotated reference. Key knobs:

| Section | Purpose |
|---------|---------|
| `poll`        | How often / how many trades to pull. |
| `filters`     | Restrict to specific markets or sides. |
| `detection`   | Thresholds for each signal type. |
| `notifications` | Console / file / webhook / Telegram. |
| `paper`       | Fake-money account + win-rate tracking. |
| `follow`      | Optional live order placement (off by default). |
| `state`       | Where the dedup/paper state is persisted. |

Secrets (`*_env` keys) are read from environment variables, never the YAML file.

---

## Architecture

```
whalebot/
  __main__.py   CLI entrypoint (run / test / report / settle)
  config.py     typed config loading + validation
  client.py     read-only Polymarket Data/Gamma API client
  models.py     Trade + Signal data models
  detector.py   the whale-detection signals
  paper.py      fake-money portfolio + win-rate stats
  notifier.py   pluggable alert delivery
  executor.py   optional live following via py-clob-client
  daemon.py     the polling loop that wires it all together
  state.py      persistent dedup / spend / paper state
tests/          unit tests (no network)
```

Run the tests with:

```bash
pip install pytest && python -m pytest
```

---

## How "suspicious" is decided

The bot treats **aggressive taker buys** (someone crossing the spread to buy) as
buying pressure. A whale about to push a price typically shows up as one or more
of: a single large buy, sustained accumulation by one wallet, or a cluster of
wallets buying the same outcome in a short window. Each is independently
configurable so you can tune sensitivity to your markets.

This is a **signal/alerting tool**, not financial advice. It surfaces unusual
flow; you decide what it means.
