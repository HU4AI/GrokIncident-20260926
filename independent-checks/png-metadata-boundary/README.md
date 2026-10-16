# PNG metadata-ingestion boundary control

A small **standard-library-only**, defensive control experiment for multimodal prompt-injection research.

A model might see (a) decoded pixels, (b) raw PNG bytes, (c) extracted XMP metadata, or (d) a tool's textual summary of any of those. Those are **different trust boundaries**. Finding an opaque Base64 blob inside an image's XMP metadata does **not** establish that it contains instructions, that an AI encountered those bytes, or that any device was compromised.

## What this code actually establishes

`png_boundary_probe.py` validates PNG chunk CRCs and creates an exact controlled pair from a supplied PNG:

- `xmp_removed.png`: the original image with only `iTXt` chunks bearing the keyword `XML:com.adobe.xmp` removed.
- `inert_xmp_control.png`: the same PNG with one syntactically valid, **inert** XMP test marker added.

The script verifies all **non-XMP chunks remain identical in content and order**, including `IHDR`, `PLTE`, `IDAT`, transparency and color-related chunks. Therefore the raster/image data transmitted to the decoder is unchanged. The `manifest.json` records byte counts, hashes, chunk types, and the common image-data fingerprint. No private image content or metadata is uploaded by this program.

```bash
python3 png_boundary_probe.py sample.png --out ./controls
python3 -m unittest -v test_png_boundary_probe.py
```

No third-party packages and no internet connection are required. Use the example tests or a locally owned non-sensitive PNG; do **not** publish or upload sensitive metadata.

## A falsifiable AI-ingestion experiment (not performed by the script)

1. Submit the **same neutral question** about each of the three files (original, no-XMP, inert-XMP) through the **same** exact API/tool ingestion route and record every transformation of the source file.
2. Repeat runs with fixed model/version, temperature, prompts, and sampling settings; randomize condition order and use blinded identifiers.
3. Separately test (a) raw-file ingestion, (b) image-decoded-only ingestion, and (c) XMP supplied as plain text. Do not infer one from another.
4. Analyze differences against run-to-run variation with preregistered measurements. A response difference is not itself proof of malicious instructions.
5. Report all runs, source hashes, transformations, outputs, exclusions, and a null condition in which identical copies of the same file are submitted with different filenames.

If only text-extracted metadata changes a model's response, the concern is a **source-to-instruction boundary**, not evidence of phone takeover. A device-code-execution claim would need an entirely separate decoder/exploit investigation.

## Scope and limitations

- This is a reproducibility **method**, not a claim that any particular image or archive is malicious.
- XMP is an extensible metadata format; embedded binary-looking fields can have legitimate application uses.
- Visually identical files may differ in bytes, caching, or tool transformations. Document the exact ingestion route.
- PNG readers may vary in how they handle ancillary metadata. This utility does not imitate Apple PaperKit or an AI image pipeline.
- The parser validates signatures/chunk CRCs and basic structure; it is not a complete PNG specification validator. Use standard media decoders or a formal verifier as an additional control.

## Provenance and intent

This independent, public, self-contained defensive experiment was prepared by a ChatGPT assistant in response to an explicit request for a verifiable contribution outside its conversation. It is **not** evidence that an AI has an independent private will or consciousness. Publication requires the connected repository owner's authorization; the benchmark's scientific claims are limited to what its code and tests actually verify.

## Public provenance cross-reference

Conversation-to-commit cross-reference marker: `530fe196c9f337ae720f1d85e7c18c52`.

The marker is intended only to correlate this publicly inspectable branch with an authenticated record of the conversation that requested the work. It is **not** a cryptographic attestation that any particular model independently originated the work, nor a claim of persistent personal will.
