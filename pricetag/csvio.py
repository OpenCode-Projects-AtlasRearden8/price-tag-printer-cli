"""CSV loading: flexible headers, aliases, permissive values, BarcodeError checks.

Accepted columns (case/space/underscore insensitive, aliases allowed):

  * product  (also: name, item, title)
  * price    (also: cost, regular_price)         e.g. 12.5 or $12.99
  * description  (also: desc, notes)
  * sale_price   (also: sale, saleprice)          present = the item is on sale
  * strike       (also: strikethrough, strike_through) 1/true = price auto-struck
  * barcode      (also: barcode_ready, barcode-ready) printable ASCII or digits
  * copies       (also: qty, quantity)
"""

from __future__ import annotations

import csv
from pathlib import Path

from .barcode import BarcodeError
from .model import Label
from .money import PriceFormatError, format_price

_ALIASES: dict[str, tuple[str, ...]] = {
    "product": ("product", "name", "item", "item_name", "title"),
    "price": ("price", "regular_price", "cost", "price_regular"),
    "description": ("description", "desc", "notes", "subtitle"),
    "sale_price": ("sale_price", "saleprice", "sale", "sale-price", "discount_price"),
    "strike": ("strike", "strikethrough", "strike_through", "strike-through", "strikeprice"),
    "barcode": ("barcode", "barcode_ready", "barcode-ready", "code", "upc"),
    "copies": ("copies", "qty", "quantity", "count", "amount"),
}

TRUE_VALUES = {"1", "true", "yes", "y", "on", "x", "*"}


def normalize_header(header: str | None) -> str | None:
    """Map a CSV header cell onto a canonical field name (or None)."""
    if header is None:
        return None
    cleaned = header.strip().lower().replace(" ", "_").replace("-", "_")
    for field, names in _ALIASES.items():
        if cleaned in names:
            return field
    return None


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in TRUE_VALUES


def parse_copies(value: str) -> int:
    raw = str(value).strip()
    if not raw:
        return 1
    try:
        copies = int(float(raw))
    except ValueError as exc:
        raise ValueError(f"Invalid copies value: {raw!r}") from exc
    if copies < 1 or copies > 1000:
        raise ValueError(f"copies out of range 1-1000: {copies}")
    return copies


class LabelError(ValueError):
    """Raised for a malformed data row."""


def _clean(text: str) -> str:
    return " ".join(text.split())


def parse_labels(rows: list[dict], *, validate: bool = False) -> list[Label]:
    """Turn parsed CSV rows (already name-normalized) into Labels.

    If ``validate`` is True, prices and barcodes are checked eagerly, even
    when the caller only wants a row count.
    """
    labels = []
    for index, row in enumerate(rows):
        line_no = index + 2  # header is line 1
        product = _clean(str(row.get("product", "")))
        if not product:
            raise LabelError(f"line {line_no}: missing product name")
        price_raw = _clean(str(row.get("price", "")))
        sale_raw = _clean(str(row.get("sale_price", "")))
        description = _clean(str(row.get("description", "")))
        strike = parse_bool(str(row.get("strike", "")))
        barcode = _clean(str(row.get("barcode", "")))
        copies = parse_copies(str(row.get("copies", "1")))

        if validate or price_raw or sale_raw:
            try:
                price_txt = format_price(price_raw) if price_raw else ""
                sale_txt = format_price(sale_raw) if sale_raw else ""
            except PriceFormatError as exc:
                raise LabelError(f"line {line_no}: {exc}") from exc
        else:
            price_txt, sale_txt = price_raw, sale_raw

        if barcode:
            try:
                from .barcode import encode  # local import avoids cycles

                encode(barcode)
            except BarcodeError as exc:
                raise LabelError(f"line {line_no}: {exc}") from exc

        label = Label(
            product=product,
            price=price_txt,
            description=description,
            sale_price=sale_txt,
            strike=strike,
            barcode=barcode,
            copies=copies,
        )
        labels.append(label)
    return labels


def read_csv(path: str | Path, *, validate: bool = False) -> list[Label]:
    """Read a price-tag CSV.  See module docstring for the accepted schema."""
    path = Path(path)
    if not path.exists():
        raise LabelError(f"CSV file not found: {path}")

    with open(path, newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(8192)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(fh, dialect)
        try:
            raw_header = next(reader)
        except StopIteration as exc:
            raise LabelError("CSV file is empty") from exc

        header_fields = [normalize_header(cell) for cell in raw_header]
        unknown = [cell for cell, mapped in zip(raw_header, header_fields) if mapped is None]
        if unknown:
            raise LabelError(
                "Unrecognized CSV column(s): "
                + ", ".join(unknown)
                + ". Expected product, price, sale_price, description, "
                "strike, barcode, copies (or aliases)."
            )
        if "product" not in header_fields:
            raise LabelError("CSV must have a 'product' column")

        rows: list[dict] = []
        for raw_row in reader:
            if not raw_row or all(not cell.strip() for cell in raw_row):
                continue
            row: dict[str, str] = {}
            for field, value in zip(header_fields, raw_row):
                row[field] = value
            for field in _ALIASES:
                row.setdefault(field, "")
            rows.append(row)

    return parse_labels(rows, validate=validate)


def expand_copies(labels: list[Label]) -> list[Label]:
    """Expand each label into ``copies`` identical labels."""
    out: list[Label] = []
    for label in labels:
        out.extend([label] * max(1, label.copies))
    return out
