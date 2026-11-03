"""Price formatting helpers for price tags."""

from __future__ import annotations

import re

_CURRENCY_RE = re.compile(r"^\s*([-+$€£¥])?\s*((\d[\d,]*)(\.\d+)?)\s*([A-Za-z]{0,3})\s*$")


class PriceFormatError(ValueError):
    """Raised when a price column cannot be interpreted."""


def format_price(value: str | float | int, currency: str = "$") -> str:
    """Format a raw price into a display string, e.g. ``12.5 -> $12.50``.

    If the value already looks like a formatted price (contains a currency
    symbol or is written with separators) it is passed through cleaned up
    rather than reformatted.
    """
    if value is None:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""

    match = _CURRENCY_RE.match(raw)
    if not match:
        raise PriceFormatError(f"Unrecognized price value: {raw!r}")

    symbol, number = match.group(1), match.group(2)
    if symbol and symbol not in {"$", "+", "-"}:
        return raw

    try:
        amount = float(number.replace(",", ""))
    except ValueError as exc:
        raise PriceFormatError(f"Unrecognized price value: {raw!r}") from exc

    text = f"{amount:,.2f}"
    if symbol == "-":
        currency = "-" + currency
    elif symbol == "+":
        currency = "+" + currency
    return f"{currency}{text}" if currency else text


def decimal_amount(value: str | float | int) -> float:
    """Return the numeric amount of a price string (for sorting, width math)."""
    raw = str(value).strip()
    match = _CURRENCY_RE.match(raw)
    if not match:
        raise PriceFormatError(f"Unrecognized price value: {raw!r}")
    return float(match.group(2).replace(",", ""))
