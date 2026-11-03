# price-tag-printer

Print-ready price tags and shelf labels from a simple CSV. Exports
**print-ready HTML and PDF** at common label sizes, with an optional
**Code 128 barcode** on every tag. Runs 100% offline on Python's standard
library — no pip dependencies, no network, no accounts.

Part of Asdale Dynamics, LLC's collection of free, small-business tools.
Plain-English tools and guides live at <https://dylanasdale.github.io>.

## Why you might want this

- You sell at markets, on eBay/Amazon, or in a small shop and need shelf
  tags fast.
- You have a printer and label stock (Avery sheets, Dymo-style rolls, or
  just cut paper) but no label software.
- You want one command that turns `inventory.csv` into something you can
  print, cut, and stick up.

## Quick start

```bash
# no install needed — works straight from this folder:
python3 -m pricetag sample/inventory.csv --format both

# or install the `pricetag` command:
pip install .
pricetag sample/inventory.csv --format both
```

That writes `tags.html` and `tags.pdf` next to your CSV. Open the HTML in
a browser (double-click it) and print at **100% scale, margins "None"** —
or print the PDF directly.

Typical commands:

```bash
pricetag inventory.csv                          # HTML for the shelf preset
pricetag inventory.csv --format pdf             # PDF (one label per page)
pricetag inventory.csv -s avery-5160 --format both   # 30-up letter sheet
pricetag inventory.csv -s 2.25x1.25 --format pdf     # custom size in inches
pricetag inventory.csv --border                 # draw a label border
pricetag inventory.csv --no-description         # skip the description line
pricetag inventory.csv --currency €             # other currency symbols
pricetag --list-sizes                           # see every label preset
```

## The CSV

A header row plus one row per product. Column names are forgiving
(case/spaces/hyphens don't matter, and aliases work).

```csv
product,price,sale_price,description,strike,barcode,qty
Duct Tape 2in x 10yd Silver,$14.99,$9.49,Heavy-duty all purpose,1,4052273130554,4
Honey Crisp Apples,$3.49,,Local orchard 3lb bag,,,3
```

| Column       | Aliases                        | Meaning                                                     |
| ------------ | ------------------------------ | ----------------------------------------------------------- |
| `product`    | name, item, title              | **required** — the big text on the tag                      |
| `price`      | regular_price, cost            | e.g. `12.5` (`$12.50`) or `$3.49` as-is                     |
| `sale_price` | sale                           | if present, the price is shown struck-through and this shown big |
| `description`| desc, notes                    | small line under the name                                   |
| `strike`     | strikethrough, strike_through  | `1`/`true`/`yes` to force strike-through styling of `price` |
| `barcode`    | barcode_ready, code            | the text to encode (digits or printable ASCII). Digits that are 4+ and even length use compact Code 128 subset C; everything else uses subset B |
| `qty`        | copies, quantity               | print multiple copies of that tag                           |

Any column can be left empty. Unrecognized columns raise an error early
rather than silently printing the wrong tag.

## Label sizes

Presets (use with `--size`): `shelf` (default 2.25 x 1.25 in), 
`dymo-30252`, `dymo-30336`, `dymo-30374`, `small-1-5`, `wide-3-1`, and
sheet presets `avery-5160`, `avery-5163`, `avery-5164`, `avery-5167`,
`avery-5168` (grid layouts on letter paper). Any `WIDTHxHEIGHT` in inches
also works, e.g. `--size 2.25x1.25`. Run `python3 -m pricetag --list-sizes`
to see them all.

Roll presets print one label per page/label; sheet presets tile a page.

## What gets produced, and how printing works

- **HTML** (`-f html`, default): one self-contained file. The bundled
  DejaVu fonts are embedded, barcodes are inline SVG, and `@page` rules
  match your label size, so Chrome/Firefox/Edge can print it directly at
  100% scale. Use `--fonts system` to skip embedding for a smaller file.
- **PDF** (`-f pdf`): a minimal PDF 1.4 document written with pure Python
  stdlib. Uses the PDF standard Helvetica fonts and vector barcode bars —
  crisp at any printer resolution, tiny file sizes.
- `--format both` writes both.

Barcode checks: Code 128 checksums and symbol patterns were verified
against the ISO/IEC 15417 reference table (cross-checked with the ZXing
decoder's tables). Quiet zones per spec are preserved. Still, always do a
test scan with your own scanner before batch printing.

## Tests

```bash
python3 -m unittest discover -s tests -t .   # stdlib only, no installs
python3 -m pytest tests                      # if pytest is available
```

## Files & layout

```
pricetag/            the package (cli, csvio, layout, htmlx, pdfgen, barcode)
pricetag/fonts/      bundled DejaVu Sans fonts + their permissive license
sample/inventory.csv example CSV
tests/               pytest/unittest test suite
LICENSE              MIT (c) 2026 Asdale Dynamics, LLC
```

## License & credits

MIT License — Copyright (c) 2026 Asdale Dynamics, LLC. The bundled
DejaVu Sans fonts carry their own permissive license, included at
`pricetag/fonts/LICENSE-DejaVu.txt`.

Built by [Asdale Dynamics, LLC](https://dylanasdale.github.io) — the
publishing arm of Dylan Asdale's plain-English AI guides (*The Massive AI
Manual*). More free beginner-friendly tools there.

## Known gaps

- PDF text uses WinAnsi; characters outside Windows-1252 become `?`
  (use the HTML output for full Unicode).
- No date/lot/expiry fields on tags yet — add a request.
- Scan-test barcodes with your own reader before production runs.
