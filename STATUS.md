# STATUS.md — price-tag-printer

Project state: **complete and verified** (first release, v1.0.0).

## What was built

A zero-dependency Python CLI (`pricetag`) that turns a simple CSV into
print-ready price tags / shelf labels.

- **Input**: one CSV row per product — `product`, `price`, `sale_price`,
  `description`, `strike`, `barcode`, `qty` (case/alias tolerant).
- **Output 1 — HTML**: one self-contained file; bundled DejaVu fonts
  embedded as base64; barcodes as inline SVG; `@page` rules match the
  label size so browsers print at 100% scale.
- **Output 2 — PDF**: minimal PDF 1.4 written with Python stdlib only.
  Vector barcodes, PDF base-14 Helvetica text, one page per label
  (roll sizes) or 30/10/6/80/4-up grid per letter sheet (Avery presets).
- **Barcodes**: Code 128 (subset C for even-length digit runs, subset B
  otherwise). Symbol table and check-digit verified against the
  ISO/IEC 15417 reference table (cross-checked with ZXing's decoder
  tables); spec quiet zones preserved.
- **Strike-through**: on-sale tags show the regular price struck and the
  sale price prominent (CSS in HTML, drawn rule in PDF); the `strike`
  column forces the styling flag explicitly.
- **16 label presets** (`--size`): shelf (2.25x1.25), dymo-30252/30336/30374,
  small-1-5, wide-3-1, and Avery sheet layouts 5160/5163/5164/5167/5168,
  plus any custom `WIDTHxHEIGHT` in inches.
- Fonts bundled under `pricetag/fonts/` with their permissive license
  (Bitstream Vera / DejaVu).

No network access is used at build or runtime; no dependencies at runtime;
no secrets or personal data anywhere in the repo.

## How to run it

```bash
# from the repo folder, no install needed:
python3 -m pricetag sample/inventory.csv --format both

# or install and use the short command:
pip install .
pricetag inventory.csv -s avery-5160 --format both
pricetag --list-sizes
```

Print the HTML in any browser (100% scale, margins "None") or print the
PDF directly.

## Verification results (this session)

- `python3 -m pytest tests` — **43 passed**
- `python3 -m unittest discover -s tests -t .` — **43 tests, OK**
- `pip install .` succeeds; installed `pricetag` command verified end to
  end (Python 3.13.5, PEP 668 environment with `--break-system-packages`
  needed locally, which is environment-specific).
- All 11 size presets generated both formats and every PDF was parsed
  and text-extracted successfully with pypdf **6.21.2 in strict mode**.
- Barcode geometry checked numerically in the generated PDF: bars sit
  centered with the required quiet-zone clearance; strike-through rules
  present exactly when a sale price exists.
- README quick-start commands executed exactly as written; sample CSV
  produces 17 labels (6 products, `qty` column honored).
- CLI error paths verified: bad format value, missing CSV, invalid size,
  and unparseable prices exit non-zero with clear messages.

## Known gaps / limitations

- PDF text is Windows-1252 only; characters outside it become `?`
  (HTML output is full Unicode — use it when needed).
- Barcodes are print-correct per spec, but were not scan-tested here
  with a physical scanner — always do one test scan.
- Only one currency symbol can be mixed per run (pass `--currency ""`
  for plain numbers).
- No date/lot/expiry fields yet; happy to add on request.
- Sheet presets print label content only; die-cut stock supplies the
  grid (blank gaps are intentional — matching the physical label layout).

## Repo layout

```
pricetag/            package: cli, csvio, money, barcode, layout, htmlx, pdfgen, presets
pricetag/fonts/      DejaVu Sans (regular + bold) + LICENSE-DejaVu.txt
sample/inventory.csv example CSV
tests/               43 tests (unittest/pytest compatible)
LICENSE              MIT — Copyright (c) 2026 Asdale Dynamics, LLC
README.md            full usage docs
```
