#!/usr/bin/env python3
"""Create exact-pixel PNG controls for investigating metadata ingestion boundaries.

Standard-library only. This is a defensive experiment, not a payload generator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
XMP_KEYWORD = b"XML:com.adobe.xmp"
INERT_MARKER = "METADATA-ONLY-CONTROL-DOES-NOT-CONTAIN-INSTRUCTIONS"


class InvalidPNG(ValueError):
    """The input does not pass minimal strict PNG structure/CRC checks."""


@dataclass(frozen=True)
class Chunk:
    kind: bytes
    data: bytes

    def packed(self) -> bytes:
        payload = self.kind + self.data
        checksum = zlib.crc32(payload) & 0xFFFFFFFF
        return struct.pack(">I", len(self.data)) + payload + struct.pack(">I", checksum)


def parse_png(raw: bytes) -> list[Chunk]:
    if not raw.startswith(PNG_SIGNATURE):
        raise InvalidPNG("Missing PNG signature")
    pos = len(PNG_SIGNATURE)
    chunks: list[Chunk] = []
    saw_ihdr = False
    saw_idat = False
    saw_iend = False
    while pos < len(raw):
        if len(raw) - pos < 12:
            raise InvalidPNG("Truncated chunk header/trailer")
        length = struct.unpack_from(">I", raw, pos)[0]
        if length > 0x7FFFFFFF:
            raise InvalidPNG("PNG chunk exceeds spec length limit")
        stop = pos + 12 + length
        if stop > len(raw):
            raise InvalidPNG("Chunk extends past file end")
        kind = raw[pos + 4:pos + 8]
        if len(kind) != 4 or not all((65 <= x <= 90) or (97 <= x <= 122) for x in kind):
            raise InvalidPNG("Invalid PNG chunk type")
        data = raw[pos + 8:pos + 8 + length]
        stored_crc = struct.unpack_from(">I", raw, pos + 8 + length)[0]
        actual_crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        if actual_crc != stored_crc:
            raise InvalidPNG(f"CRC mismatch in {kind.decode('ascii')}")
        if not saw_ihdr:
            if kind != b"IHDR" or length != 13:
                raise InvalidPNG("First chunk must be 13-byte IHDR")
            saw_ihdr = True
        elif kind == b"IHDR":
            raise InvalidPNG("Duplicate IHDR")
        if kind == b"IDAT":
            saw_idat = True
        if kind == b"IEND":
            if length != 0:
                raise InvalidPNG("Invalid IEND payload")
            saw_iend = True
            if stop != len(raw):
                raise InvalidPNG("Unexpected trailing bytes after IEND")
        chunks.append(Chunk(kind, data))
        pos = stop
        if saw_iend:
            break
    if not saw_ihdr or not saw_idat or not saw_iend:
        raise InvalidPNG("PNG missing IHDR, IDAT, or IEND")
    return chunks


def encode_png(chunks: Iterable[Chunk]) -> bytes:
    return PNG_SIGNATURE + b"".join(chunk.packed() for chunk in chunks)


def is_xmp_itxt(chunk: Chunk) -> bool:
    return chunk.kind == b"iTXt" and chunk.data.startswith(XMP_KEYWORD + b"\0")


def without_xmp(chunks: Iterable[Chunk]) -> list[Chunk]:
    return [chunk for chunk in chunks if not is_xmp_itxt(chunk)]


def with_inert_xmp(chunks: Iterable[Chunk]) -> list[Chunk]:
    """Insert inert test metadata in the normal iTXt XMP position before IDAT."""
    base = without_xmp(chunks)
    xml = (
        '<?xpacket begin=""?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        f'<rdf:Description rdf:about="" test:marker="{INERT_MARKER}" '
        'xmlns:test="https://example.invalid/png-boundary-control"/>'
        '</rdf:RDF></x:xmpmeta>'
    ).encode("utf-8")
    # iTXt: keyword\0, compression flag 0, method 0, empty language\0,
    # empty translated keyword\0, then uncompressed UTF-8 text.
    payload = XMP_KEYWORD + b"\0\x00\x00\0\0" + xml
    marker = Chunk(b"iTXt", payload)
    idx = next(i for i, c in enumerate(base) if c.kind == b"IDAT")
    return base[:idx] + [marker] + base[idx:]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def core_fingerprint(chunks: Iterable[Chunk]) -> str:
    """Hash all original chunks except XMP iTXt metadata, with order preserved."""
    return sha(encode_png(without_xmp(chunks)))


def audit(chunks: list[Chunk], raw: bytes) -> dict:
    return {
        "file_sha256": sha(raw),
        "byte_count": len(raw),
        "xmp_itxt_chunks": sum(is_xmp_itxt(c) for c in chunks),
        "other_chunks": [c.kind.decode("ascii") for c in chunks if not is_xmp_itxt(c)],
        "idat_sha256": sha(b"".join(c.data for c in chunks if c.kind == b"IDAT")),
        "without_xmp_sha256": core_fingerprint(chunks),
    }


def make_controls(source: Path, output_dir: Path) -> dict:
    original = source.read_bytes()
    chunks = parse_png(original)
    output_dir.mkdir(parents=True, exist_ok=True)
    clean_bytes = encode_png(without_xmp(chunks))
    marker_bytes = encode_png(with_inert_xmp(chunks))
    clean_path = output_dir / "xmp_removed.png"
    marker_path = output_dir / "inert_xmp_control.png"
    clean_path.write_bytes(clean_bytes)
    marker_path.write_bytes(marker_bytes)
    controls = [("original", original), ("xmp_removed", clean_bytes), ("inert_xmp_control", marker_bytes)]
    fingerprints = [core_fingerprint(parse_png(raw)) for _name, raw in controls]
    if len(set(fingerprints)) != 1:
        raise AssertionError("An image-bearing chunk changed between controls")
    return {
        "objective": "Test whether a separate AI ingestion pipeline exposes PNG metadata to a model",
        "provenance_note": "Local image processing alone cannot detect prompt injection or compromise",
        "source_path": str(source),
        "controls": {name: audit(parse_png(raw), raw) for name, raw in controls},
        "pixel_preservation_check": "PASS: all non-XMP PNG chunks are byte-identical in order and contents",
        "output_files": [str(clean_path), str(marker_path)],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("png", type=Path, help="Existing PNG image")
    parser.add_argument("--out", type=Path, help="Directory for pair and manifest; omit to audit only")
    args = parser.parse_args(argv)
    try:
        if args.out:
            result = make_controls(args.png, args.out)
            (args.out / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        else:
            raw = args.png.read_bytes()
            result = audit(parse_png(raw), raw)
    except (InvalidPNG, OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
