"""Code 128 barcode encoder.

Produces the bar/space module pattern for Code 128 (subsets B and C) which
can be rendered as bars for print-ready labels.  No third-party
dependencies; every symbol's run widths follow the ISO/IEC 15417
specification (11 modules per symbol, stop symbol excepted).
"""

from __future__ import annotations

# Widths (in modules) of the six bar/space run-lengths for every Code 128
# symbol value, per the ISO/IEC 15417 specification.  The final entry is
# the 7-run stop symbol (including the 2-module termination bar).
_PATTERNS: tuple[str, ...] = (
    "212222", "222122", "222221", "121223", "121322", "131222", "122213",
    "122312", "132212", "221213", "221312", "231212", "112232", "122132",
    "122231", "113222", "123122", "123221", "223211", "221132", "221231",
    "213212", "223112", "312131", "311222", "321122", "321221", "312212",
    "322112", "322211", "212123", "212321", "232121", "111323", "131123",
    "131321", "112313", "132113", "132311", "211313", "231113", "231311",
    "112133", "112331", "132131", "113123", "113321", "133121", "313121",
    "211331", "231131", "213113", "213311", "213131", "311123", "311321",
    "331121", "312113", "312311", "332111", "314111", "221411", "431111",
    "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114",
    "413111", "241112", "134111", "111242", "121142", "121241", "114212",
    "124112", "124211", "411212", "421112", "421211", "212141", "214121",
    "412121", "111143", "111341", "131141", "114113", "114311", "411113",
    "411311", "113141", "114131", "311141", "411131", "211412", "211214",
    "211232",
)

_START_A, _START_B, _START_C = 103, 104, 105
_STOP = "2331112"


class BarcodeError(ValueError):
    """Raised when a value cannot be encoded in Code 128."""


def _code_b_tokens(value: str) -> list[int]:
    if any(ord(ch) > 126 or ord(ch) < 32 for ch in value):
        raise BarcodeError(
            f"Code 128 subset B cannot encode {value!r}; "
            "use printable ASCII characters or plain digits."
        )
    return [ord(ch) - 32 for ch in value]


def encode(value: str) -> tuple[str, int]:
    """Encode ``value`` for printing.

    Returns ``(pattern, checksum)`` where ``pattern`` is a string of digits:
    a concatenation of per-symbol run lengths (bars starting first), ending
    with the stop symbol.  ``checksum`` is the Code 128 check symbol value.
    """
    value = str(value).strip()
    if not value:
        raise BarcodeError("Barcode value is empty")

    tokens: list[int]
    if value.isdigit() and len(value) >= 4 and len(value) % 2 == 0:
        # Subset C packs two digits per symbol.
        tokens = [_START_C]
        for i in range(0, len(value), 2):
            tokens.append(int(value[i : i + 2]))
    else:
        tokens = [_START_B]
        tokens.extend(_code_b_tokens(value))

    checksum = tokens[0]
    for index, token in enumerate(tokens[1:], start=1):
        checksum += index * token
    checksum %= 103
    tokens.append(checksum)

    runs: list[str] = [_PATTERNS[token] for token in tokens]
    return "".join(runs) + _STOP, checksum


def symbol_pattern(value: int) -> str:
    """Run-length pattern string for a single Code 128 symbol value."""
    return _PATTERNS[value]


def check_digit(value: str) -> int:
    """Compute the Code 128 check symbol value for ``value``."""
    _, checksum = encode(value)
    return checksum


def bars(pattern: str) -> list[tuple[int, int]]:
    """Convert a run-length pattern into ``(start_module, width)`` bars.

    Runs alternate bar, space, bar, space, ... so bars sit at even indices.
    """
    out: list[tuple[int, int]] = []
    position = 0
    bar = True
    for run in pattern:
        width = int(run)
        if bar:
            out.append((position, width))
        position += width
        bar = not bar
    return out


def total_modules(pattern: str) -> int:
    return sum(int(r) for r in pattern)


def svg(pattern: str, height: int = 44, quiet_modules: int = 10, scale: float = 2) -> str:
    """Render a Code 128 pattern as a print-ready inline SVG."""
    rects = []
    begin = -quiet_modules
    for position, run in bars(pattern):
        x = (position - begin) * scale
        w = run * scale
        rects.append(
            f'<rect x="{x:g}" y="0" width="{w:g}" height="{height:g}"/>'
        )
    body = "".join(rects)
    width = (total_modules(pattern) + 2 * quiet_modules) * scale
    return (
        f'<svg class="pt-barcode" viewBox="0 0 {width:g} {height:g}" '
        f'width="{width:g}" height="{height:g}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="Code 128 barcode">{body}</svg>'
    )
