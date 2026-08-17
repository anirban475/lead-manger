#!/usr/bin/env python3
"""
ACTION-001: OCR Test Script
Runs deterministic OCR (Tesseract with hin+eng language data) on a newspaper page image
and writes literal extracted text to a .md file next to the input image.
"""

import os
import sys
import subprocess
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 ocr_test.py <path-to-image>", file=sys.stderr)
        sys.exit(1)

    image_path = Path(sys.argv[1]).resolve()
    if not image_path.exists():
        print(f"Error: Input image file not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    # Output markdown path alongside the image
    md_path = image_path.with_suffix(".md")

    # Run mechanical OCR using tesseract (Hindi + English)
    cmd = [
        "tesseract",
        str(image_path),
        "stdout",
        "-l",
        "hin+eng"
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    except FileNotFoundError:
        print("Error: tesseract binary not found in PATH", file=sys.stderr)
        sys.exit(1)

    if res.returncode != 0:
        print(f"Error: Tesseract failed with exit code {res.returncode}:\n{res.stderr}", file=sys.stderr)
        sys.exit(res.returncode)

    raw_text = res.stdout.strip()
    if not raw_text:
        print("Error: OCR produced no text at all.", file=sys.stderr)
        sys.exit(1)

    # Write literal extracted text directly to the markdown file
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# OCR Extraction: {image_path.name}\n\n")
        f.write(raw_text)
        f.write("\n")

    print(f"Successfully processed {image_path.name} -> {md_path.name} ({len(raw_text)} chars extracted)")
    sys.exit(0)


if __name__ == "__main__":
    main()
