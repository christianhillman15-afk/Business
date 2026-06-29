"""Polymarket whale-watching bot.

A config-driven daemon that monitors Polymarket trade flow, flags suspicious
buying activity that may signal a whale about to push a price, alerts the
operator, and can optionally follow the trade through the official CLOB client.
"""

__version__ = "0.1.0"
