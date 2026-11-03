"""Common label size presets (inches) and how to lay them out.

Two layout styles exist:

* single-label sizes (thermal/roll labels): one label per page;
* sheet sizes (die-cut sheets): a grid of labels on letter paper.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Size


@dataclass(frozen=True)
class Preset:
    key: str
    label: Size
    sheet: tuple[float, float] | None = None  # inches; None = one per page
    grid: tuple[int, int] | None = None  # (columns, rows) across the sheet
    margins: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)  # top,right,bottom,left
    gap: tuple[float, float] = (0.0, 0.0)
    description: str = ""


def _nearest_preset(size: Size) -> Preset | None:
    """Preset whose label size matches within 0.01 in, if any."""
    for preset in PRESETS.values():
        if (
            abs(preset.label.width - size.width) < 0.01
            and abs(preset.label.height - size.height) < 0.01
        ):
            return preset
    return None


PRESETS: dict[str, Preset] = {
    "shelf": Preset(
        key="shelf",
        label=Size(2.25, 1.25),
        description="2.25 x 1.25 in shelf label (Monarch / retail tag)",
    ),
    "dymo-30252": Preset(
        key="dymo-30252",
        label=Size(2.125, 1.125),
        description="Dymo 30252 address label, 2.125 x 1.125 in roll",
    ),
    "dymo-30336": Preset(
        key="dymo-30336",
        label=Size(1, 1),
        description="Dymo 30336 square label, 1 x 1 in roll",
    ),
    "dymo-30374": Preset(
        key="dymo-30374",
        label=Size(1.125, 3.5),
        description="Dymo 30374 name badge 1.125 x 3.5 in roll",
    ),
    "small-1-5": Preset(
        key="small-1-5",
        label=Size(1.5, 1),
        description="Small 1.5 x 1 in tag, good for jewelry or bins",
    ),
    "wide-3-1": Preset(
        key="wide-3-1",
        label=Size(3, 1),
        description="Wide 3 x 1 in strip label",
    ),
    "avery-5160": Preset(
        key="avery-5160",
        label=Size(2.625, 1),
        sheet=(8.5, 11),
        grid=(3, 10),
        margins=(0.5, 0.1875, 0.5, 0.15625),
        gap=(0.125, 0.0),
        description="Avery 5160 sheet, 30 labels of 2.625 x 1 in on letter paper",
    ),
    "avery-5163": Preset(
        key="avery-5163",
        label=Size(4, 2),
        sheet=(8.5, 11),
        grid=(2, 5),
        margins=(0.5, 0.34375, 0.15625, 0.15625),
        gap=(0.0, 0.0),
        description="Avery 5163 sheet, 10 labels of 4 x 2 in on letter paper",
    ),
    "avery-5164": Preset(
        key="avery-5164",
        label=Size(4.0, 3.3333333333),
        sheet=(8.5, 11),
        grid=(2, 3),
        margins=(0.5, 0.156, 0.156, 0.156),
        gap=(0.188, 0.0),
        description="Avery 5164 sheet, 6 labels of 4 x 3.33 in on letter paper",
    ),
    "avery-5167": Preset(
        key="avery-5167",
        label=Size(1.75, 0.5),
        sheet=(8.5, 11),
        grid=(4, 20),
        margins=(0.5, 0.2875, 0.1875, 0.1875),
        gap=(0.25, 0.0),
        description="Avery 5167 return-address sheet, 80 labels of 1.75 x 0.5 in",
    ),
    "avery-5168": Preset(
        key="avery-5168",
        label=Size(3.5, 5),
        sheet=(8.5, 11),
        grid=(2, 2),
        margins=(0.5, 0.1875, 0.1875, 0.8125),
        gap=(0.0, 0.0),
        description="Avery 5168 shipping sheet, 4 labels of 3.5 x 5 in",
    ),
}


def find_preset(name: str) -> Preset | None:
    """Look up a preset by key, tolerant of separators and prefixes."""
    if not name:
        return None
    cleaned = name.strip().lower().replace(" ", "-").replace("_", "-")
    return PRESETS.get(cleaned)


def resolve_size(name: str) -> tuple[Preset | None, Size]:
    """Resolve '--size' user input to a Preset (or None) plus a Size.

    Accepted forms: preset key ('shelf'), or 'WIDTH HEIGHT', or
    'WIDTHxHEIGHT' in inches, fractions allowed (e.g. 2.25x1.25).
    """
    cleaned = (name or "").strip().lower()
    preset = find_preset(cleaned)
    if preset:
        return preset, preset.label
    normalized = cleaned.replace(" ", "x").replace("*", "x").replace(",", "x")
    width, sep, height = normalized.partition("x")
    if sep:
        try:
            size = Size(float(width), float(height))
        except ValueError as exc:
            raise ValueError(f"Could not parse label size {name!r}") from exc
        return _nearest_preset(size), size
    raise ValueError(f"Could not parse label size {name!r}")


def preset_for_size(size: Size) -> Preset | None:
    """Preset (possibly a sheet style) whose label matches ``size``."""
    return _nearest_preset(size)


def describe_presets() -> str:
    lines = []
    for preset in PRESETS.values():
        lines.append(f"  {preset.key:14s}  {preset.description}")
    return "\n".join(lines)
