"""End-to-end CLI tests via subprocess and unittest."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pricetag import __version__

REPO = Path(__file__).parent.parent
SAMPLE = REPO / "sample" / "inventory.csv"


def _run(args, cwd=None, tmp_home=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "pricetag", *[str(a) for a in args]],
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )


class CliHelpTests(unittest.TestCase):
    def test_version_and_help(self):
        done = _run(["--version"])
        self.assertEqual(done.returncode, 0)
        self.assertIn(__version__, done.stdout)
        help_done = _run(["--help"])
        self.assertEqual(help_done.returncode, 0)
        self.assertIn("--size", help_done.stdout)

    def test_list_sizes(self):
        done = _run(["--list-sizes"])
        self.assertEqual(done.returncode, 0)
        self.assertIn("shelf", done.stdout)
        self.assertIn("avery-5160", done.stdout)


class CliConversionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pt-cli-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_sample_csv_end_to_end(self):
        out = Path(self.tmp) / "tags"
        done = _run([SAMPLE, "-o", out, "--format", "both"])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((Path(self.tmp) / "tags.html").exists())
        self.assertTrue((Path(self.tmp) / "tags.pdf").exists())
        self.assertIn("17 labels", done.stdout)

        from pypdf import PdfReader

        reader = PdfReader(str(Path(self.tmp) / "tags.pdf"))
        self.assertEqual(len(reader.pages), 17)  # 4+3+1+6+1(default qty)+2

    def test_custom_size_and_error_handling(self):
        out = Path(self.tmp) / "wide"
        done = _run([SAMPLE, "-s", "3x2", "-o", out, "--format", "pdf"])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((Path(self.tmp) / "wide.pdf").exists())

        bad = _run([SAMPLE, "-s", "not-a-size", "-o", Path(self.tmp) / "x"])
        self.assertEqual(bad.returncode, 2)
        self.assertIn("error", bad.stderr.lower())

        missing = _run([Path(self.tmp) / "nope.csv"])
        self.assertEqual(missing.returncode, 2)

    def test_bad_conversion_exit_code(self):
        bad_csv = Path(self.tmp) / "bad.csv"
        bad_csv.write_text("product,price\nThing,free\n", encoding="utf-8")
        done = _run([bad_csv, "-o", Path(self.tmp) / "x"])
        self.assertEqual(done.returncode, 2)
        self.assertIn("error", done.stderr.lower())

    def test_default_output_beside_csv(self):
        workdir = Path(self.tmp) / "work"
        workdir.mkdir()
        (workdir / "items.csv").write_text(
            "product,price\nWidget,$9.55\n", encoding="utf-8"
        )
        done = _run(["items.csv", "--format", "html"], cwd=workdir)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((workdir / "items.html").exists())
        self.assertIn("Widget", (workdir / "items.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
