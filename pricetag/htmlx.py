"""Self-contained print-ready HTML export.

Produces one HTML file with:
* the bundled DejaVu fonts embedded as base64 data URIs (works offline);
* an optional system-font mode for a smaller file;
* exact label dimensions in CSS points shared with the PDF layout;
* inline SVG barcodes;
* @page rules so browsers print page-sized labels directly.
"""

from __future__ import annotations

import base64
import html
from pathlib import Path

from .layout import PT_PER_IN, Plan, PlanConfig, plan_label
from .model import Label, Size
from .presets import Preset

FONTS_DIR = Path(__file__).parent / "fonts"
TOOLS_URL = "https://dylanasdale.github.io"


def _font_uri(name: str) -> str:
    data = (FONTS_DIR / name).read_bytes()
    return "data:font/ttf;base64," + base64.b64encode(data).decode("ascii")


def font_faces_css(embed: bool) -> str:
    """@font-face rules, or a plain font stack fallback when not embedding."""
    if not embed:
        return "/* fonts not embedded; using system font stack */"
    return (
        "@font-face { font-family: 'DejaVu Sans'; "
        f"src: url({_font_uri('DejaVuSans.ttf')}) format('truetype'); "
        "font-weight: normal; font-display: block; }\n"
        "@font-face { font-family: 'DejaVu Sans'; "
        f"src: url({_font_uri('DejaVuSans-Bold.ttf')}) format('truetype'); "
        "font-weight: bold; font-display: block; }"
    )


def page_css(size: Size, preset: Preset | None) -> str:
    """@page rules plus the label container layout."""
    label_w = size.width * PT_PER_IN
    label_h = size.height * PT_PER_IN
    container = (
        ".pt-label { width: %gpt; height: %gpt; box-sizing: border-box; "
        "overflow: hidden; }" % (label_w, label_h)
    )
    if preset is not None and preset.sheet and preset.grid:
        cols, _rows = preset.grid
        top, right, bottom, left = [m * PT_PER_IN for m in preset.margins]
        sheet_w = preset.sheet[0] * PT_PER_IN
        sheet_h = preset.sheet[1] * PT_PER_IN
        page = (
            f"@page {{ size: {sheet_w:g}pt {sheet_h:g}pt; margin: 0; }}\n"
            ".pt-sheet { width: %gpt; height: %gpt; box-sizing: border-box; "
            "padding: %gpt %gpt %gpt %gpt; display: grid; "
            "grid-template-columns: repeat(%d, %gpt); "
            "row-gap: %gpt; column-gap: %gpt; }"
            % (sheet_w, sheet_h, top, right, bottom, left, cols, label_w, preset.gap[1], preset.gap[0])
        )
        return page + "\n" + container
    page = f"@page {{ size: {label_w:g}pt {label_h:g}pt; margin: 0; }}"
    return page + "\n" + container


def _label_html(label: Label, plan: Plan, index: int) -> str:
    sc = html.escape
    name = sc(label.product)
    desc = (
        f'<div class="pt-desc" style="font-size: {plan.desc_size:g}pt">'
        f"{sc(label.description)}</div>"
        if label.description
        else ""
    )
    if label.on_sale:
        struck = sc(label.price)
        price_block = (
            f'<div class="pt-was" style="font-size: {plan.orig_size:g}pt">'
            f"<s>{struck}</s></div>"
            f'<div class="pt-now" style="font-size: {plan.price_size:g}pt">'
            f"{sc(label.sale_price)}</div>"
        )
    elif label.price:
        price_block = (
            f'<div class="pt-price" style="font-size: {plan.price_size:g}pt">'
            f"{sc(label.price)}</div>"
        )
    else:
        price_block = ""

    barcode_html = ""
    if plan.uses_barcode:
        for prim in plan.primitives:
            if prim["op"] != "barcode":
                continue
            svg = _barcode_svg(label.barcode, height=prim["h"], width=prim["w"])
            digits = (
                f'<div class="pt-bcdigits" style="font-size: {prim["digit_size"]:g}pt">'
                f'{sc(prim["digits"])}</div>'
                if prim["digits"]
                else ""
            )
            barcode_html = f'<div class="pt-barcode">{svg}{digits}</div>'
            break

    return (
        f'<div class="pt-label" aria-label="Price tag {index + 1}: {name}">'
        f'<div class="pt-name" style="font-size: {plan.name_size:g}pt">{name}</div>'
        f"{desc}{price_block}{barcode_html}</div>"
    )


def _barcode_svg(barcode: str, height: float, width: float) -> str:
    from . import barcode as bc

    pattern, _check = bc.encode(barcode)
    return bc.svg(pattern, height=height, quiet_modules=0, scale=width / bc.total_modules(pattern))


def render_html_document(
    labels: list[Label],
    size: Size,
    preset: Preset | None,
    config: PlanConfig,
    *,
    embed_fonts: bool = True,
) -> str:
    """Render all labels into one printable, self-contained HTML document."""
    if not labels:
        raise ValueError("No labels to render; the CSV appears to have no data rows")

    labels = labels[:4000]
    per_sheet = 0
    sheet_css_present = preset is not None and preset.sheet and preset.grid
    if sheet_css_present:
        per_sheet = int(preset.grid[0] * preset.grid[1])

    css = font_faces_css(embed_fonts) + "\n" + page_css(size, preset)
    body: list[str] = []
    chunk: list[str] = []
    for counter, label in enumerate(labels):
        plan = plan_label(label, size, config)
        chunk.append(_label_html(label, plan, counter))
        if per_sheet and len(chunk) >= per_sheet:
            body.append('<div class="pt-sheet">' + "".join(chunk) + "</div>")
            chunk = []
    if chunk:
        if per_sheet:
            body.append('<div class="pt-sheet">' + "".join(chunk) + "</div>")
        else:
            body.extend(chunk)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Price tags — {len(labels)} label(s), {size.width:g} x {size.height:g} in</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
{css}
* {{ margin: 0; padding: 0; }}
body {{ font-family: 'DejaVu Sans', 'Helvetica Neue', Arial, sans-serif;
       background: #f2f2f2; color: #000; }}
.pt-label {{ position: relative; background: #fff; padding: 5pt;
         font-family: 'DejaVu Sans', 'Helvetica Neue', Arial, sans-serif;
         display: flex; flex-direction: column; align-items: stretch; }}
.pt-name {{ font-weight: bold; text-align: center; line-height: 1.1;
         overflow: hidden; }}
.pt-desc {{ line-height: 1.05; text-align: left; margin-top: 1.5pt; overflow: hidden; }}
.pt-price {{ font-weight: bold; text-align: center; margin-top: auto; line-height: 1.1; }}
.pt-was {{ font-weight: bold; text-align: center; margin-top: auto; line-height: 1.15; }}
.pt-was s {{ text-decoration: line-through; text-decoration-thickness: 0.8pt; }}
.pt-now {{ font-weight: bold; text-align: center; line-height: 1.1; }}
.pt-barcode {{ margin-top: auto; text-align: center; }}
.pt-barcode svg {{ display: inline-block; shape-rendering: crispEdges; }}
.pt-bcdigits {{ letter-spacing: 0.4pt; text-align: center; line-height: 1.1; }}
@media screen {{
  .pt-label, .pt-sheet {{ margin: 10px auto; box-shadow: 0 1px 6px rgba(0,0,0,.25); }}
  .pt-hint {{ max-width: 640px; margin: 12px auto; font-size: 12px; color: #555;
             font-family: 'DejaVu Sans', 'Helvetica Neue', Arial, sans-serif; }}
}}
@media print {{
  body {{ background: none; margin: 0; }}
  .pt-hint {{ display: none; }}
  .pt-label {{ page-break-after: always; break-after: page; }}
  .pt-sheet {{ page-break-after: always; break-after: page; }}
  .pt-sheet .pt-label, .pt-label:last-child {{ page-break-after: auto; break-after: auto; }}
}}
</style>
</head>
<body>
<p class="pt-hint">Print at 100% scale with margins set to “None”.
Generated by price-tag-printer — Asdale Dynamics, LLC — {TOOLS_URL}</p>
{"".join(body)}
</body>
</html>
"""
