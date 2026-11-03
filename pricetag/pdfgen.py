"""Minimal print-ready PDF writer (PDF 1.4) built on the Python stdlib.

Non-interactive PDFs with one page per label (or a grid of labels per
letter-size sheet).  Text uses the PDF base-14 Helvetica fonts; barcodes
are drawn as vector rectangles, so output prints crisply at any zoom and
needs no external libraries or fonts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .layout import PT_PER_IN, Plan, PlanConfig, plan_label
from .model import Label, Size
from .presets import Preset

PAGE_LIMIT = 4000

_F_REG = "F1"
_F_BOLD = "F2"


def _fmt(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _esc(text: str) -> str:
    """Sanitize text to Windows-1252 and escape PDF string syntax."""
    out = []
    for ch in text:
        try:
            cp = ch.encode("cp1252")[0]
        except (UnicodeEncodeError, IndexError):
            cp = ord("?")
        if cp > 126:
            out.append("?")
        else:
            out.append(chr(cp))
    cleaned = "".join(out)
    return cleaned.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


@dataclass
class PageBox:
    """One PDF page; ``slots`` are label origins from the top-left, pt."""

    width: float
    height: float
    slots: list[tuple[float, float]] = field(default_factory=list)


def pages_for(labels: list[Label], size: Size, preset: Preset | None) -> list[PageBox]:
    """Pagination: one label per page, or grid slots for sheet presets."""
    box_w = size.width * PT_PER_IN
    box_h = size.height * PT_PER_IN
    if preset is None or preset.sheet is None or preset.grid is None:
        return [PageBox(width=box_w, height=box_h, slots=[(0.0, 0.0)]) for _ in labels]

    sheet_w = preset.sheet[0] * PT_PER_IN
    sheet_h = preset.sheet[1] * PT_PER_IN
    top, right, bottom, left = [m * PT_PER_IN for m in preset.margins]
    vx, vy = preset.gap
    cols, rows = preset.grid

    slots: list[tuple[float, float]] = []
    for row in range(rows):
        for col in range(cols):
            x = left + col * (box_w + vx)
            y = top + row * (box_h + vy)
            if y + box_h <= sheet_h - bottom + 0.01 and x + box_w <= sheet_w - right + 0.01:
                slots.append((x, y))
    if not slots:
        raise ValueError("Sheet preset leaves no room for its own label size")

    pages: list[PageBox] = []
    for start in range(0, min(len(labels), PAGE_LIMIT), len(slots)):
        pages.append(PageBox(width=sheet_w, height=sheet_h, slots=slots))
    return pages


def _plan_operations(plan: Plan, origin: tuple[float, float], page_h: float) -> list[bytes]:
    """PDF content-stream operators for one plan, translated to the slot origin."""
    sx, sy = origin
    ops = [b"0 0 0 rg 0 0 0 RG"]

    def x(v: float) -> float:
        return sx + v

    def y(v: float) -> float:
        return page_h - (sy + v)

    for prim in plan.primitives:
        op = prim["op"]
        if op == "frame":
            ops.append(
                (
                    f"0.75 w {_fmt(x(prim['x']))} {_fmt(y(prim['y'] + prim['h']))} "
                    f"{_fmt(prim['w'])} {_fmt(prim['h'])} re S"
                ).encode()
            )
        elif op == "strike":
            t = prim["t"]
            ops.append(
                (
                    f"{_fmt(x(prim['x']))} {_fmt(y(prim['y'] + t))} "
                    f"{_fmt(prim['w'])} {_fmt(t)} re f"
                ).encode()
            )
        elif op == "text":
            font = _F_BOLD if prim["font"] == "bold" else _F_REG
            ops.append(
                (
                    f"BT /{font} {_fmt(prim['size'])} Tf "
                    f"1 0 0 1 {_fmt(x(prim['x']))} {_fmt(y(prim['y']))} Tm "
                    f"({_esc(prim['text'])}) Tj ET"
                ).encode()
            )
        elif op == "barcode":
            for off, run in prim["bars"]:
                if run <= 0:
                    continue
                ops.append(
                    (
                        f"{_fmt(x(prim['x'] + off))} {_fmt(y(prim['y'] + prim['h']))} "
                        f"{_fmt(run)} {_fmt(prim['h'])} re f"
                    ).encode()
                )
    return ops


def render_pdf_document(
    labels: list[Label],
    size: Size,
    preset: Preset | None,
    config: PlanConfig,
) -> bytes:
    """Render labels to a complete PDF document as bytes."""
    labels = labels[:PAGE_LIMIT]
    if not labels:
        raise ValueError("No labels to render; the CSV appears to have no data rows")
    pages = pages_for(labels, size, preset)
    plans = [plan_label(label, size, config) for label in labels]

    stream_objs: list[list[bytes]] = []
    for page_index, page in enumerate(pages):
        cap = len(page.slots)
        ops: list[bytes] = []
        for slot_index, slot in enumerate(page.slots):
            label_index = page_index * cap + slot_index
            if label_index >= len(plans):
                break
            ops.extend(_plan_operations(plans[label_index], slot, page.height))
        stream_objs.append(ops)

    return _assemble(pages, stream_objs)


def _assemble(pages: list[PageBox], stream_ops: list[list[bytes]]) -> bytes:
    """Build the PDF file: header, objects, xref, trailer."""
    objects: dict[int, bytes] = {}

    font_reg = (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>"
    )
    font_bold = (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
        b"/Encoding /WinAnsiEncoding >>"
    )

    page_ids: list[int] = []
    content_ids: list[int] = []
    next_id = 5
    for page, ops in zip(pages, stream_ops):
        page_ids.append(next_id)
        content_ids.append(next_id + 1)
        content_id = next_id + 1
        stream = b"\n".join(ops).rstrip(b"\n")
        objects[content_id] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode()
            + stream
            + b"\nendstream"
        )
        next_id += 2

    for page_id, page, content_id in zip(page_ids, pages, content_ids):
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_fmt(page.width)} "
            f"{_fmt(page.height)}] /Resources << /Font << /{_F_REG} 3 0 R "
            f"/{_F_BOLD} 4 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode()

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = (
        f"<< /Type /Pages /Count {len(pages)} /Kids [{kids}] >>".encode()
    )
    objects[3] = font_reg
    objects[4] = font_bold

    total = max(objects) + 1

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = [0] * (total + 1)
    for object_id in range(1, total):
        body = objects.get(object_id)
        if body is None:
            continue
        offsets[object_id] = len(out)
        out.extend(f"{object_id} 0 obj\n".encode())
        out.extend(body)
        out.extend(b"\nendobj\n")

    xref_pos = len(out)
    out.extend(f"xref\n0 {total}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for object_id in range(1, total):
        if objects.get(object_id) is not None:
            out.extend(f"{offsets[object_id]:010d} 00000 n \n".encode())
        else:
            out.extend(b"0000000000 65535 f \n")
    out.extend(
        (
            f"trailer\n<< /Size {total} /Root 1 0 R "
            f"/Info << /Title (Price Tags) /Producer (price-tag-printer) "
            f"/Creator (price-tag-printer) >> >>\nstartxref\n{xref_pos}\n%%EOF\n"
        ).encode()
    )
    return bytes(out)
