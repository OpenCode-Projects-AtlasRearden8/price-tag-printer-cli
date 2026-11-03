"""Command-line interface for price-tag-printer."""

from __future__ import annotations

import argparse
import pathlib
import sys

from . import __version__
from .csvio import expand_copies, read_csv
from .htmlx import render_html_document
from .layout import PlanConfig
from .pdfgen import render_pdf_document
from .presets import describe_presets, resolve_size

FORMAT_CHOICES = ("html", "pdf", "both")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pricetag",
        description=(
            "Print price tags and shelf labels from a simple CSV. "
            "Exports print-ready HTML and PDF; no network, no extra installs."
        ),
        epilog="Version %s — part of Asdale Dynamics, LLC's free tools." % __version__,
    )
    parser.add_argument(
        "csv",
        nargs="?",
        default=None,
        help="input CSV file (see README for the schema)",
    )
    parser.add_argument(
        "-o",
        "--out",
        default=None,
        help="output file basename (default: the CSV name with a new extension)",
    )
    parser.add_argument(
        "--format",
        choices=FORMAT_CHOICES,
        default="html",
        help="output format (default: html)",
    )
    parser.add_argument(
        "-s",
        "--size",
        default="shelf",
        help=(
            "label size: a preset key ('shelf', 'dymo-30252', 'avery-5160', ...) "
            "or WIDTHxHEIGHT in inches (e.g. 2.25x1.25)"
        ),
    )
    parser.add_argument("--border", action="store_true", help="draw a label border")
    parser.add_argument(
        "--no-description",
        action="store_true",
        help="omit the description even when the CSV has one",
    )
    parser.add_argument(
        "--currency",
        default="$",
        metavar="SYM",
        help='currency symbol (default "$"; use --currency "" for plain numbers)',
    )
    parser.add_argument(
        "--fonts",
        choices=("embed", "system"),
        default="embed",
        help="HTML font handling: embed the bundled DejaVu fonts (default) "
        "or rely on the system font stack",
    )
    parser.add_argument(
        "--list-sizes",
        action="store_true",
        help="list label size presets and exit",
    )
    parser.add_argument(
        "--version", action="version", version="price-tag-printer " + __version__
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_sizes:
        print("Label size presets (use with --size):")
        print(describe_presets())
        return 0

    if not args.csv:
        parser.error("the following arguments are required: csv")

    try:
        labels = read_csv(args.csv, validate=True)
        if not labels:
            raise ValueError(f"No data rows found in {args.csv}")
        labels = expand_copies(labels)
        preset, size = resolve_size(args.size)
        config = PlanConfig(
            border=args.border,
            show_description=not args.no_description,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out = pathlib.Path(args.out) if args.out else pathlib.Path(args.csv).with_suffix("")
    base = out if out.suffix == "" else out.with_suffix("")
    written: list[str] = []
    try:
        if args.format in ("html", "both"):
            html_doc = render_html_document(
                labels,
                size,
                preset,
                config,
                embed_fonts=args.fonts == "embed",
            )
            html_path = base.with_suffix(".html")
            html_path.write_text(html_doc, encoding="utf-8")
            written.append(str(html_path))
        if args.format in ("pdf", "both"):
            pdf_bytes = render_pdf_document(labels, size, preset, config)
            pdf_path = base.with_suffix(".pdf")
            pdf_path.write_bytes(pdf_bytes)
            written.append(str(pdf_path))
    except Exception as exc:
        print(f"error rendering labels: {exc}", file=sys.stderr)
        return 3

    size_name = preset.key if preset else "%gx%g in" % (size.width, size.height)
    print(
        "wrote %d label%s at %s -> %s"
        % (
            len(labels),
            "" if len(labels) == 1 else "s",
            size_name,
            ", ".join(written),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
