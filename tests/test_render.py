"""Tests for the layout engine and PDF/HTML renderers."""

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from pricetag.layout import (
    PlanConfig,
    fit_text_size,
    plan_label,
    text_width,
    wrap_text,
)
from pricetag.model import Label, Size
from pricetag.presets import resolve_size

SHELF = Size(2.25, 1.25)


class MetricsTests(unittest.TestCase):
    def test_text_width_matches_helvetica_metrics(self):
        # 3 digits x 556 units per 1000 em -> at 10pt = 16.68pt
        self.assertAlmostEqual(text_width("111", size=10.0), 16.68)
        # lowercase 'a' is 556 regular, 611 bold
        bold_wider = text_width("aaa", bold=True, size=12.0)
        regular = text_width("aaa", bold=False, size=12.0)
        self.assertGreater(bold_wider, regular)

    def test_fit_text_size_shrinks_for_wide_text(self):
        fits = fit_text_size("Hello", 200.0, 14.0, bold=True)
        tight = fit_text_size("Hello World Goodbye", 30.0, 14.0, bold=True)
        self.assertEqual(fits, 14.0)
        self.assertLess(tight, 14.0)

    def test_wrap_text_greedy(self):
        lines = wrap_text("one two three four", 40.0, 10.0)
        self.assertLessEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("one"))

    def test_wrap_text_adds_ellipsis_on_overflow(self):
        lines = wrap_text("extraordinarilylongunbrokenword", 50.0, 10.0, max_lines=2)
        self.assertTrue(lines[-1].endswith("..."))


class PlanTests(unittest.TestCase):
    def test_plan_positions_within_bounds(self):
        label = Label(
            product="Duct Tape 2in x 10yd Silver Heavy Duty",
            price="$14.99",
            sale_price="$9.49",
            description="All purpose",
            barcode="4052273130554",
        )
        plan = plan_label(label, SHELF, PlanConfig(border=True))
        for prim in plan.primitives:
            if prim["op"] == "text":
                self.assertTrue(0 <= prim["x"] <= plan.width, prim)
                self.assertTrue(0 <= prim["y"] <= plan.height, prim)
            if prim["op"] == "strike":
                self.assertGreaterEqual(prim["x"], 0)
                self.assertGreater(prim["w"], 0)
            if prim["op"] == "barcode":
                self.assertGreaterEqual(prim["x"], 0)
                self.assertLessEqual(prim["x"] + prim["w"], plan.width + 0.01)

    def test_plan_strikes_the_regular_price_when_on_sale(self):
        label = Label(product="Widget", price="$10.00", sale_price="$7.00")
        plan = plan_label(label, SHELF, PlanConfig())
        texts = [p["text"] for p in plan.primitives if p["op"] == "text"]
        strikes = [p for p in plan.primitives if p["op"] == "strike"]
        self.assertIn("$10.00", texts)
        self.assertIn("$7.00", texts)
        self.assertEqual(len(strikes), 1)

    def test_plan_ignores_strike_without_sale(self):
        label = Label(product="Widget", price="$10.00", strike=True)
        plan = plan_label(label, SHELF, PlanConfig())
        self.assertFalse(any(p["op"] == "strike" for p in plan.primitives))

    def test_plan_no_barcode_when_absent(self):
        label = Label(product="Just a price", price="$1.00")
        plan = plan_label(label, Size(1, 1), PlanConfig())
        self.assertFalse(plan.uses_barcode)
        self.assertFalse(any(p["op"] == "barcode" for p in plan.primitives))

    def test_small_label_still_fits(self):
        label = Label(
            product="Enormous Product Name That Is Quite Long Indeed",
            price="$999.99",
            sale_price="$899.99",
            description="An overly wordy description goes here to stress layout",
            barcode="052188112211",
        )
        plan = plan_label(label, Size(1, 1), PlanConfig(border=True))
        self.assertEqual(plan.width, 72)
        self.assertEqual(plan.height, 72)
        for prim in plan.primitives:
            if prim["op"] == "strike":
                self.assertGreaterEqual(prim["x"], 0.0)
                self.assertLessEqual(prim["x"] + prim["w"], 72.01)


class PdfTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pt-pdf-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    @staticmethod
    def _read_pages(data: bytes):
        assert data.startswith(b"%PDF-1.4")
        assert data.rstrip().endswith(b"%%EOF")
        pages = re.findall(rb"/Type /Page[^s].*?>>", data, re.S)
        boxes = re.findall(rb"/MediaBox \[0 0 ([0-9.]+) ([0-9.]+)\]", data)
        return pages, boxes

    def test_pdf_structure_and_page_sizes(self):
        from pricetag.pdfgen import render_pdf_document

        labels = [Label("First", "$1.00"), Label("Second", "$2.00"), Label("Third", "$3.00")]
        data = render_pdf_document(labels, SHELF, None, PlanConfig())
        pages, boxes = self._read_pages(data)
        self.assertEqual(len(pages), 3)
        self.assertTrue(all(w == b"162" and h == b"90" for w, h in boxes))
        path = Path(self.tmp) / "out.pdf"
        path.write_bytes(data)
        self.assertGreater(path.stat().st_size, 500)

        from pypdf import PdfReader

        reader = PdfReader(str(path))
        self.assertEqual(len(reader.pages), 3)
        self.assertIn("First", reader.pages[0].extract_text())
        self.assertIn("Third", reader.pages[2].extract_text())

    def test_pdf_sheet_paging(self):
        from pricetag.pdfgen import render_pdf_document

        labels = [Label(f"Item {i}", "$1.00") for i in range(31)]
        preset, size = resolve_size("avery-5160")
        data = render_pdf_document(labels, size, preset, PlanConfig())
        pages, boxes = self._read_pages(data)
        # 30 labels per sheet -> 2 pages, second has 1 label
        self.assertEqual(len(pages), 2)
        self.assertTrue(all((w, h) == (b"612", b"792") for w, h in boxes))

    def test_pdf_rejects_empty(self):
        from pricetag.pdfgen import render_pdf_document

        with self.assertRaises(ValueError):
            render_pdf_document([], SHELF, None, PlanConfig())


class HtmlTests(unittest.TestCase):
    def test_html_self_contained_and_labelled(self):
        from pricetag.htmlx import render_html_document

        labels = [Label("Tea Kettle", "$24.00", sale_price="$19.00"), Label("Mug", "$4.00")]
        doc = render_html_document(labels, SHELF, None, PlanConfig())
        self.assertEqual(doc.count('class="pt-label"'), 2)
        self.assertIn("<s>$24.00</s>", doc)
        self.assertIn("$19.00", doc)
        self.assertIn("data:font/ttf;base64,", doc)
        self.assertIn("@page", doc)
        self.assertGreaterEqual(doc.count("DejaVu Sans"), 5)

    def test_html_sheet_grid(self):
        from pricetag.htmlx import render_html_document

        labels = [Label("Item", "$1") for _ in range(4)]
        preset, size = resolve_size("avery-5160")
        doc = render_html_document(labels, size, preset, PlanConfig(), embed_fonts=False)
        self.assertEqual(doc.count('<div class="pt-sheet">'), 1)

    def test_html_barcode_svg_present(self):
        from pricetag.htmlx import render_html_document

        doc = render_html_document(
            [Label("Coded", "$5", barcode="12345678")], SHELF, None, PlanConfig(),
            embed_fonts=False,
        )
        self.assertIn('<svg class="pt-barcode"', doc)


if __name__ == "__main__":
    unittest.main()
