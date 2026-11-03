"""Tests for Code 128 barcode encoding (patterns verified against ZXing's
ISO/IEC 15417 reference table)."""

import unittest

from pricetag.barcode import (
    BarcodeError,
    _PATTERNS,
    _STOP,
    bars,
    check_digit,
    encode,
    svg,
    symbol_pattern,
    total_modules,
)


class BarcodeTests(unittest.TestCase):
    def test_start_codes_match_the_spec(self):
        self.assertEqual(symbol_pattern(103), "211412")  # Start A
        self.assertEqual(symbol_pattern(104), "211214")  # Start B
        self.assertEqual(symbol_pattern(105), "211232")  # Start C
        self.assertEqual(_STOP, "2331112")

    def test_every_symbol_is_11_modules(self):
        for i, pattern in enumerate(_PATTERNS):
            self.assertEqual(
                sum(int(r) for r in pattern), 11, f"symbol {i} bad: {pattern}"
            )
        self.assertEqual(sum(int(r) for r in _STOP), 13)

    def test_subset_b_text_encoding(self):
        pattern, check = encode("HI")
        # Start B + 'H' + 'I': check = (104 + 1*40 + 2*41) % 103 = 20
        self.assertEqual(check, 20)
        self.assertTrue(pattern.startswith(symbol_pattern(104)))

    def test_check_digit_is_consistent(self):
        self.assertEqual(check_digit("0123456789"), 73)
        self.assertEqual(check_digit("HELLO-123"), check_digit("HELLO-123"))
        _, check = encode("HELLO-123")
        self.assertEqual(check, check_digit("HELLO-123"))

    def test_subset_c_for_even_digit_runs(self):
        pattern, _ = encode("1234")
        self.assertTrue(pattern.startswith("211232"))  # start C
        self.assertNotEqual(pattern, encode("abcd")[0])

    def test_subset_b_for_odd_digits(self):
        pattern, _ = encode("123")
        self.assertTrue(pattern.startswith("211214"))  # start B

    def test_bars_alternate_and_cover_the_module_run(self):
        out = bars("212222")  # symbol 0: bar, space, ... = 2,1,2,2,2,2
        self.assertEqual(out, [(0, 2), (3, 2), (7, 2)])

    def test_total_modules_counts_everything(self):
        self.assertEqual(total_modules("212222" + "2331112"), 11 + 13)

    def test_svg_is_printable_inline_markup(self):
        pattern, _ = encode("1234")
        markup = svg(pattern, height=40, quiet_modules=0, scale=2)
        self.assertTrue(markup.startswith("<svg"))
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', markup)
        self.assertIn("/svg>", markup)

    def test_rejects_control_characters(self):
        with self.assertRaises(BarcodeError):
            encode("bad\nvalue")

    def test_rejects_empty_value(self):
        with self.assertRaises(BarcodeError):
            encode("   ")


if __name__ == "__main__":
    unittest.main()
