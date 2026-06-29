# Getting started — step by step

This guide gets the whale bot watching **all of Polymarket** and recording
flagged trades into your **$1,000 paper account**. No coding required — just
copy/paste the commands.

> The bot watches every market by default. "Suspicious" = any trade that crosses
> your thresholds (big single buys, one wallet accumulating, lots of wallets
> piling in, or a wallet on your watchlist). You can loosen/tighten these later
> in `config.yaml`.

---

## Before you pick where to run it

The bot is a **daemon** — it must keep running to keep watching. Your options:

| Option | Stays on 24/7? | Difficulty | Best for |
|--------|----------------|------------|----------|
| **Your own computer** | Only while it's awake | Easiest | Trying it out |
| **A cloud server (VPS)** | Yes, always | Medium | Real use — recommended |
| **Docker** | Yes (on any host) | Medium | If you know Docker |

Pick one below.

---

## Option A — Run on your own computer (easiest)

**1. Install Python 3.11+** if you don't have it: https://www.python.org/downloads/

**2. Get the code** (in a terminal / Command Prompt):
```bash
git clone https://github.com/christianhillman15-afk/Business.git
cd Business
git checkout claude/polymarket-trading-bot-x4525o
```

**3. Install the bot:**
```bash
pip install -r requirements.txt
```

**4. Create your config:**
```bash
cp config.example.yaml config.yaml          # Windows: copy config.example.yaml config.yaml
```

**5. Test it once** (pulls live trades, prints what it would flag):
```bash
python -m whalebot test
```
You should see 🐋 alerts and a paper-account summary.

**6. Run it for real:**
```bash
python -m whalebot run
```
Leave that window open. Press `Ctrl+C` to stop.

**7. Check your win rate anytime** (in another terminal, same folder):
```bash
python -m whalebot report
```

That's it. The catch: it stops watching when your computer sleeps or shuts down.
For always-on, use Option B or C.

---

## Option B — Run on a cloud server (always-on, ~$5/mo)

Get a cheap Linux VPS (DigitalOcean, Hetzner, Vultr, AWS Lightsail). Choose
Ubuntu. Then SSH in and:

```bash
# install python + git
sudo apt update && sudo apt install -y python3 python3-venv git

# get the code
sudo git clone https://github.com/christianhillman15-afk/Business.git /opt/whalebot
cd /opt/whalebot
sudo git checkout claude/polymarket-trading-bot-x4525o

# install into a virtual environment
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r requirements.txt

# create your config
sudo cp config.example.yaml config.yaml
```

Now install it as a background service so it runs 24/7 and restarts on reboot:

```bash
sudo cp deploy/whalebot.service /etc/systemd/system/whalebot.service
sudo systemctl daemon-reload
sudo systemctl enable --now whalebot
```

**Watch the live alerts:**
```bash
journalctl -u whalebot -f
```

**See your win rate:**
```bash
cd /opt/whalebot && sudo .venv/bin/python -m whalebot report
```

**Stop / start:** `sudo systemctl stop whalebot` / `sudo systemctl start whalebot`

---

## Option C — Docker (any host)

```bash
git clone https://github.com/christianhillman15-afk/Business.git
cd Business && git checkout claude/polymarket-trading-bot-x4525o
cp config.example.yaml config.yaml
cp .env.example .env          # optional: fill in if you use Telegram/Discord
docker compose up -d --build  # start in the background
docker compose logs -f        # watch alerts
```
Your paper ledger, state, and alerts persist in the project folder. Win rate:
```bash
docker compose exec whalebot python -m whalebot report
```

---

## Turn on phone notifications (recommended for all-market watching)

Watching all of Polymarket = lots of alerts. Get them pushed to your phone.

### Telegram (free, easiest)
1. In Telegram, message **@BotFather**, send `/newbot`, follow prompts → it gives
   you a **bot token**.
2. Message your new bot once (say "hi") so it can reply to you.
3. Get your **chat id**: open
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and copy
   the `"chat":{"id":...}` number.
4. In `config.yaml` set:
   ```yaml
   notifications:
     telegram:
       enabled: true
       chat_id: "123456789"     # your chat id
   ```
5. Put the token in `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC...
   ```
6. Restart the bot.

### Discord / Slack
1. Create an **Incoming Webhook** in your server/channel settings → copy the URL.
2. In `config.yaml` set `notifications.webhook.enabled: true`.
3. Put the URL in `.env`:
   ```
   WHALEBOT_WEBHOOK_URL=https://discord.com/api/webhooks/....
   ```
4. Restart the bot.

---

## Tuning what counts as "suspicious"

Edit `config.yaml` → `detection:` and restart. Lower numbers = more alerts.

```yaml
detection:
  large_trade_usd: 5000        # flag single buys >= this $ (lower = more alerts)
  accumulation:
    min_total_usd: 10000       # one wallet stacking this much
  coordinated:
    min_wallets: 4             # this many wallets into one outcome fast
    min_total_usd: 15000
  watchlist:
    wallets: ["0x..."]         # always alert on these known whales
```

Start with the defaults, let the **paper account** run for a couple of weeks, and
check `python -m whalebot report`. If the win rate holds up, *then* consider live
trading (see README — it's off by default and gated behind safety caps).

---

## FAQ

**Do I need a Polymarket account or money?** No — detection and paper trading are
read-only and use fake money. You only need real funds/wallet keys if you later
turn on live "follow" mode.

**Will I lose my win-rate history if it restarts?** No — it's saved to
`whalebot_state.json` and `paper_ledger.jsonl` and reloaded on start.

**It's not flagging much.** Lower the thresholds in `config.yaml` (see above).
Run `python -m whalebot test` to see current flow immediately.
