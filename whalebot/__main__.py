"""Command-line entrypoint:  python -m whalebot <command> [--config config.yaml]

Commands:
  run       start the polling daemon (default)
  report    print the current paper-account stats and exit
  settle    force a one-off settlement pass against market resolutions
  test      do a single poll cycle and exit (smoke test / cron-friendly)
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
from .daemon import WhaleBot


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _load_dotenv() -> None:
    """Load a .env file if python-dotenv is installed (optional)."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="whalebot", description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "report", "settle", "test"],
    )
    parser.add_argument("-c", "--config", default="config.yaml", help="path to config YAML")
    args = parser.parse_args(argv)

    _load_dotenv()

    try:
        cfg = load_config(args.config)
    except FileNotFoundError:
        print(f"config file not found: {args.config}", file=sys.stderr)
        print("copy config.example.yaml to config.yaml to get started.", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    _setup_logging(cfg.log_level)
    bot = WhaleBot(cfg)

    if args.command == "run":
        bot.run()
    elif args.command == "report":
        print(bot.paper.report())
    elif args.command == "settle":
        settled = bot.paper.settle(bot.client.resolve_market)
        print(f"settled {len(settled)} position(s)")
        bot.state.paper = bot.paper.to_blob()
        bot.state.save()
        print(bot.paper.report())
    elif args.command == "test":
        bot.tick()
        print(bot.paper.report())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
