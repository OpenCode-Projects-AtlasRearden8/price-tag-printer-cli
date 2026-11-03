"""Shared label layout engine.

Computes exact positions for every element of a label in points (1/72 in),
with a top-left origin.  Both the HTML and PDF renderers consume this plan,
so the two outputs agree.

Text metrics use the standard Adobe AFM widths for Helvetica and
Helvetica-Bold (PDF base-14 fonts), which are metric-compatible with Arial
and every PDF viewer's built-in Helvetica.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import Label, Size

PT_PER_IN = 72.0

# Adobe AFM character widths (units of 1/1000 em) for the base-14 fonts,
# for printable ASCII 32..126.
_W_REG = (
    "278 278 355 556 556 889 667 191 333 333 389 584 278 333 278 278 556 "
    "556 556 556 556 556 556 556 556 556 278 278 584 584 584 556 1015 "
    "667 667 722 722 667 611 778 722 278 500 667 556 833 722 778 667 778 "
    "722 667 611 722 667 944 667 667 611 278 278 278 469 556 333 556 556 "
    "500 556 556 278 556 556 222 222 500 222 833 556 556 556 556 333 500 "
    "278 556 500 722 500 500 500 334 260 334 584"
)

_W_BOLD = (
    "278 333 474 556 556 889 722 238 333 333 389 584 278 333 278 278 556 "
    "556 556 556 556 556 556 556 556 556 333 333 584 584 584 611 975 722 "
    "722 722 722 667 611 778 722 278 556 722 611 833 722 778 667 778 722 "
    "667 611 722 667 944 667 667 611 333 278 333 584 556 333 611 611 556 "
    "611 556 333 611 611 278 278 556 278 889 611 611 611 611 389 556 333 "
    "611 556 778 556 556 500 389 280 389 584"
)

_WIDTHS: dict[bool, dict[int, int]] = {
    False: {i + 32: int(w) for i, w in enumerate(_W_REG.split())},
    True: {i + 32: int(w) for i, w in enumerate(_W_BOLD.split())},
}

# Widths (per 1000 em) for common typographic characters excluded from
# the ASCII range (matching Helvetica metrics closely enough for layout).
_EXTRA_WIDTHS = {
    ord("\u20ac"): 556,  # euro sign
    ord("\u2014"): 1000,  # em dash
    ord("\u2013"): 556,  # en dash
    ord("\u2018"): 222,
    ord("\u2019"): 222,
    ord("\u201c"): 333,
    ord("\u201d"): 333,
    ord("\u2026"): 1000,  # ellipsis
    ord("\u2022"): 350,  # bullet
    ord("\u00a9"): 737,
    ord("\u00ae"): 737,
    ord("\u2122"): 556,
}

LEAD = 1.06  # line height per unit of font size


def char_width(code: int, bold: bool) -> int:
    table = _WIDTHS[bold]
    return table.get(code, _EXTRA_WIDTHS.get(code, 556))


def text_width(text: str, *, bold: bool = False, size: float) -> float:
    """Width of ``text`` in points at ``size`` pt."""
    total = sum(char_width(ord(ch), bold) for ch in text)
    return total * size / 1000.0


def fit_text_size(
    text: str,
    max_width: float,
    start_size: float,
    *,
    bold: bool = False,
    min_size: float = 6.0,
) -> float:
    """Largest font size <= start_size at which ``text`` fits one line."""
    if not text:
        return start_size
    size = start_size
    while size > min_size and text_width(text, bold=bold, size=size) > max_width:
        size -= 0.5
    return size


def wrap_text(
    text: str,
    max_width: float,
    size: float,
    *,
    bold: bool = False,
    max_lines: int = 2,
) -> list[str]:
    """Greedy word wrap to ``max_lines`` lines, with ellipsis on overflow."""
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = ""
    used = 0
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or text_width(candidate, bold=bold, size=size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            used += len(current.split())
            current = word
            if len(lines) == max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
        used += len(current.split())
    overflow = used < len(words) or any(
        text_width(line, bold=bold, size=size) > max_width for line in lines
    )
    if overflow and lines:
        last = lines[-1]
        marker = "..."
        while last and text_width(last + marker, bold=bold, size=size) > max_width:
            last = last[:-1]
        lines[-1] = (last + marker).strip() if last.strip() else marker
    return lines


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class PlanConfig:
    """Knobs for the layout engine."""

    border: bool = False
    show_description: bool = True
    pad: float = 5.0  # pt
    grip: float = 3.0  # min gap between groups (pt)


@dataclass
class BarcodeBlock:
    x: float
    width: float
    height: float
    bars: list[tuple[float, float]]  # (x_offset, width) relative to x
    digits: str = ""
    digit_size: float = 0.0


@dataclass
class Plan:
    """Exactly positioned drawing primitives, top-left origin, points."""

    width: float
    height: float
    primitives: list[dict] = field(default_factory=list)
    uses_barcode: bool = False
    name_size: float = 10.0
    desc_size: float = 7.5
    price_size: float = 12.0
    orig_size: float = 8.0
    digit_size: float = 6.0


def plan_label(label: Label, size: Size, config: PlanConfig) -> Plan:
    """Compute drawing primitives for one label."""
    width = size.width * PT_PER_IN
    height = size.height * PT_PER_IN
    inset = 1.5 if config.border else 0.0
    pad = config.pad + inset
    inner_w = width - 2 * pad
    avail_h = height - 2 * pad
    primitives: list[dict] = []

    if config.border:
        primitives.append(
            {"op": "frame", "x": 0.75, "y": 0.75, "w": width - 1.5, "h": height - 1.5}
        )

    barcode_block = _plan_barcode(label, width, height, pad) if label.has_barcode else None

    price_size0 = clamp(height * 0.22, 9.0, 20.0)
    name_size0 = clamp(height * 0.19, 8.0, 18.0)
    desc_size = clamp(height * 0.115, 6.0, 9.0)

    scale = 1.0
    chosen: dict[str, float] = {
        "name": 10.0, "desc": 7.5, "price": 12.0, "orig": 8.0, "digits": 6.0,
    }
    for _attempt in range(6):
        rows: list[tuple[str, float, list[str]]] = []  # (kind, size, lines)
        total_h = 0.0

        name_size = fit_text_size(
            label.product, inner_w, name_size0 * scale, bold=True, min_size=6.0
        )
        name_lines = wrap_text(label.product, inner_w, name_size, bold=True, max_lines=2)
        rows.append(("name", name_size, name_lines))
        total_h += LEAD * name_size * len(name_lines) + config.grip

        if config.show_description and label.description:
            desc_lines = wrap_text(label.description, inner_w, desc_size * scale, max_lines=2)
            rows.append(("desc", desc_size * scale, desc_lines))
            total_h += LEAD * desc_size * scale * len(desc_lines) + config.grip

        target = label.sale_price or label.price
        if target:
            price_size = fit_text_size(target, inner_w, price_size0 * scale, bold=True, min_size=6.0)
            if label.on_sale:
                orig_size = clamp(price_size * 0.68, 6.0, 14.0)
                total_h += 1.6 * orig_size + 1.2 * price_size
                rows.append(("price_strike", orig_size, [label.price]))
                rows.append(("price", price_size, [label.sale_price]))
            else:
                total_h += 1.2 * price_size
                rows.append(("price", price_size, [label.price]))
            total_h += config.grip

        bar_total = 0.0
        if barcode_block is not None:
            bh = barcode_block.height * scale
            digits_h = 0.45 * barcode_block.digit_size * scale if barcode_block.digits else 0.0
            bar_total = bh + digits_h + config.grip
            total_h += bar_total

        if total_h <= avail_h or scale <= 0.55:
            for kind, size, _lines in rows:
                if kind == "name":
                    chosen["name"] = size
                elif kind == "desc":
                    chosen["desc"] = size
                elif kind == "price":
                    chosen["price"] = size
                elif kind == "price_strike":
                    chosen["orig"] = size
            if barcode_block is not None and barcode_block.digits:
                chosen["digits"] = barcode_block.digit_size * scale
            break
        scale = max(0.55, scale * (avail_h / total_h) ** 0.9)

    def emit_text(y_top: float, text: str, bold: bool, size: float, align: str = "center") -> None:
        tw = text_width(text, bold=bold, size=size)
        if align == "center":
            x = (width - tw) / 2.0
        elif align == "right":
            x = width - pad - tw
        else:
            x = pad
        primitives.append(
            {
                "op": "text",
                "x": x,
                "y": y_top + 0.78 * size,
                "font": "bold" if bold else "reg",
                "size": size,
                "text": text,
            }
        )

    y = pad
    for kind, size, lines in rows:
        if kind == "name":
            for line in lines:
                emit_text(y, line, True, size)
                y += LEAD * size
        elif kind == "desc":
            for line in lines:
                emit_text(y, line, False, size, align="left")
                y += LEAD * size
        elif kind == "price_strike":
            line = lines[0]
            tw = text_width(line, bold=True, size=size)
            x = (width - tw) / 2.0
            primitives.append(
                {
                    "op": "text",
                    "x": x,
                    "y": y + 0.78 * size,
                    "font": "bold",
                    "size": size,
                    "text": line,
                }
            )
            primitives.append(
                {
                    "op": "strike",
                    "x": x,
                    "y": y + 0.78 * size - 0.12 * size,
                    "w": tw,
                    "t": max(0.6, 0.08 * size),
                }
            )
            y += 1.6 * size
        elif kind == "price":
            for line in lines:
                emit_text(y, line, True, size)
                y += 1.2 * size

    if barcode_block is not None:
        bh = barcode_block.height * scale
        digits = barcode_block.digits
        digit_size = barcode_block.digit_size * scale
        if digit_size < 4.5:
            digits = ""
        digits_h = 0.45 * digit_size if digits else 0.0
        y_bar = height - pad - bh - digits_h
        em = barcode_block.width
        primitives.append(
            {
                "op": "barcode",
                "x": (width - em) / 2.0,
                "y": y_bar,
                "w": em,
                "h": bh,
                "bars": [
                    (off * em / barcode_block.width, run * em / barcode_block.width)
                    for off, run in barcode_block.bars
                ],
                "digits": digits,
                "digit_size": digit_size,
            }
        )
        if digits:
            emit_text(y_bar + bh + 0.2 * digit_size, digits, False, digit_size)

    return Plan(
        width=width,
        height=height,
        primitives=primitives,
        uses_barcode=label.has_barcode,
        name_size=chosen["name"],
        desc_size=chosen["desc"],
        price_size=chosen["price"],
        orig_size=chosen["orig"],
        digit_size=chosen["digits"],
    )


def _plan_barcode(label: Label, width: float, height: float, pad: float) -> BarcodeBlock:
    from . import barcode as bc

    pattern, _ = bc.encode(label.barcode)
    modules = bc.total_modules(pattern)
    quiet = 10  # ISO/IEC 15417 minimum quiet zone for scanners
    avail_w = min(width - 2 * pad, 160.0)
    module_w = avail_w / (modules + 2 * quiet)
    bar_w_total = module_w * modules
    bar_h = clamp(height * 0.24, 10.0, 26.0)
    bars = [(off * module_w, run * module_w) for off, run in bc.bars(pattern)]
    keep_digits = width >= 110 and bar_w_total >= 60
    return BarcodeBlock(
        x=(width - bar_w_total) / 2.0,
        width=bar_w_total,
        height=bar_h,
        bars=bars,
        digits=label.barcode if keep_digits else "",
        digit_size=6.0,
    )
