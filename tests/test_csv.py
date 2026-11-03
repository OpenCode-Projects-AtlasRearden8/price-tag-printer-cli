"""Tests for CSV parsing, aliases, and label expansion."""

import shutil
import tempfile
import unittest
from pathlib import Path

from pricetag.csvio import LabelError, expand_copies, normalize_header, read_csv
from pricetag.model import Label
from pricetag.money import PriceFormatError, format_price

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "supply.csv"


class PriceFormatTests(unittest.TestCase):
    def test_format_price_basic(self):
        self.assertEqual(format_price("12.5"), "$12.50")
        self.assertEqual(format_price("1200"), "$1,200.00")
        self.assertEqual(format_price("$3.49"), "$3.49")
        self.assertEqual(format_price("\u20ac9,99"), "\u20ac9,99")  # pass-through

    def test_format_price_empty_and_errors(self):
        self.assertEqual(format_price(""), "")
        self.assertEqual(format_price(None), "")
        with self.assertRaises(PriceFormatError):
            format_price("free")


class ColumnTests(unittest.TestCase):
    def test_column_alias_normalization(self):
        self.assertEqual(normalize_header(" Item Name "), "product")
        self.assertEqual(normalize_header("Qty"), "copies")
        self.assertEqual(normalize_header("STRIKE-THROUGH"), "strike")
        self.assertEqual(normalize_header("barcode_ready"), "barcode")
        self.assertIsNone(normalize_header("top-secret"))


class CsvReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pt-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def write(self, name, content, encoding="utf-8"):
        path = Path(self.tmp) / name
        path.write_text(content, encoding=encoding)
        return path

    def test_read_sample_csv(self):
        labels = read_csv(SAMPLE, validate=True)
        self.assertEqual(labels[0].product, "Duct Tape 2in x 10yd Silver")
        self.assertEqual(labels[0].price, "$14.99")
        self.assertEqual(labels[0].sale_price, "$9.49")
        self.assertTrue(labels[0].strike)
        self.assertEqual(labels[0].barcode, "4052273130554")
        self.assertEqual(labels[0].copies, 4)
        plain = labels[1]
        self.assertEqual(plain.sale_price, "")
        self.assertFalse(plain.on_sale)
        self.assertFalse(plain.has_barcode)

    def test_alias_header_file(self):
        p = self.write("aliases.csv", "Item Name,Regular Price,Sale,QTY\nThing-a-ma-jig,$5,$4.25,2\n")
        labels = read_csv(p)
        self.assertEqual(labels[0].product, "Thing-a-ma-jig")
        self.assertEqual(labels[0].price, "$5.00")
        self.assertEqual(labels[0].sale_price, "$4.25")
        self.assertEqual(labels[0].copies, 2)
        self.assertTrue(labels[0].on_sale)

    def test_missing_required_column(self):
        p = self.write("bad.csv", "price,desc\n$2,thing\n")
        with self.assertRaises(LabelError):
            read_csv(p)

    def test_bad_price_reports_line(self):
        p = self.write("bad-price.csv", "product,price\nFine,1.25\nBroken,free\n")
        with self.assertRaises(LabelError) as ctx:
            read_csv(p, validate=True)
        self.assertIn("line 3", str(ctx.exception))

    def test_bad_barcode_reports_line(self):
        p = self.write("bad-barcode.csv", 'product,barcode\nBad,"ctrl\x01char"\nOK,1234\n')
        with self.assertRaises(LabelError) as ctx:
            read_csv(p, validate=True)
        self.assertIn("line 2", str(ctx.exception))

    def test_missing_file(self):
        with self.assertRaises(LabelError):
            read_csv(Path(self.tmp) / "nope.csv")

    def test_strikethrough_columns(self):
        p = self.write("strike.csv", "product,price,strikethrough\nWas-only,$9.99,yes\nKeep,$9.99,no\n")
        labels = read_csv(p)
        self.assertTrue(labels[0].strike)
        self.assertFalse(labels[1].strike)


class ExpandTests(unittest.TestCase):
    def test_expand_copies(self):
        labels = [
            Label("A", "$1", copies=3),
            Label("B", "$2", copies=1),
        ]
        expanded = expand_copies(labels)
        self.assertEqual([label.product for label in expanded], ["A", "A", "A", "B"])


if __name__ == "__main__":
    unittest.main()
