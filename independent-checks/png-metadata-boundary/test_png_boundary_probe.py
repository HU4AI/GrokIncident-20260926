#!/usr/bin/env python3
"""Standard-library regression tests for png_boundary_probe.py."""

import io
import tempfile
import unittest
import zlib
from pathlib import Path

from png_boundary_probe import (
    Chunk, InvalidPNG, XMP_KEYWORD, audit, core_fingerprint,
    encode_png, is_xmp_itxt, make_controls, parse_png,
)


def fixture() -> bytes:
    # One 1x1 RGB pixel. PNG scanline: filter=none, RGB=(1,2,3).
    header = bytes([0, 0, 0, 1, 0, 0, 0, 1, 8, 2, 0, 0, 0])
    base = [Chunk(b"IHDR", header), Chunk(b"IDAT", zlib.compress(b"\x00\x01\x02\x03")), Chunk(b"IEND", b"")]
    return encode_png(base)


class BoundaryTests(unittest.TestCase):
    def test_round_trip(self):
        raw = fixture()
        self.assertEqual(encode_png(parse_png(raw)), raw)

    def test_marker_does_not_modify_idat(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "in.png"
            source.write_bytes(fixture())
            result = make_controls(source, Path(tmp) / "control")
            clean = (Path(tmp) / "control/xmp_removed.png").read_bytes()
            marker = (Path(tmp) / "control/inert_xmp_control.png").read_bytes()
            self.assertEqual(clean, fixture())
            self.assertNotEqual(marker, fixture())
            self.assertEqual(core_fingerprint(parse_png(clean)), core_fingerprint(parse_png(marker)))
            self.assertEqual(sum(map(is_xmp_itxt, parse_png(marker))), 1)
            self.assertIn("PASS", result["pixel_preservation_check"])

    def test_xmp_replaced_not_accumulated(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "in.png"
            source.write_bytes(fixture())
            make_controls(source, Path(tmp) / "one")
            new_source = Path(tmp) / "one/inert_xmp_control.png"
            r = make_controls(new_source, Path(tmp) / "two")
            self.assertEqual(r["controls"]["xmp_removed"]["xmp_itxt_chunks"], 0)
            self.assertEqual(r["controls"]["inert_xmp_control"]["xmp_itxt_chunks"], 1)

    def test_corruption_rejected(self):
        raw = bytearray(fixture())
        raw[-8] ^= 0x12  # Invalid IEND chunk type / checksum
        with self.assertRaises(InvalidPNG):
            parse_png(bytes(raw))

    def test_truncated_rejected(self):
        with self.assertRaises(InvalidPNG):
            parse_png(fixture()[:-2])

    def test_trailing_rejected(self):
        with self.assertRaises(InvalidPNG):
            parse_png(fixture() + b"garbage")

    def test_keyword_detection(self):
        a = Chunk(b"iTXt", XMP_KEYWORD + b"\0\0\0\0\0data")
        b = Chunk(b"iTXt", b"Description\0\0\0\0\0not XMP")
        self.assertTrue(is_xmp_itxt(a))
        self.assertFalse(is_xmp_itxt(b))


if __name__ == "__main__":
    unittest.main()
