#!/usr/bin/env python3
"""
Tesseract OCR HTTP Service
Provides a lightweight HTTP wrapper around Tesseract OCR for n8n workflows.
Exposes POST /ocr accepting multipart file upload or base64 encoded JSON.
Binds to 172.21.0.1:5050 (docker bridge gateway for amatec-net).
"""

import os
import io
import re
import time
import base64
import argparse
import tempfile
import subprocess
from PIL import Image
from flask import Flask, request, jsonify

app = Flask(__name__)

# Max payload size: 32MB
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

LANG_PATTERN = re.compile(r"^[a-zA-Z0-9+_]+$")


class OCRTimeoutError(Exception):
    """Raised when Tesseract execution times out."""
    pass


class OCRExecutionError(Exception):
    """Raised when Tesseract execution fails with an error."""
    pass


def get_ocr_timeout() -> int:
    """Read Tesseract timeout from OCR_TIMEOUT_SECONDS env var, defaulting to 300."""
    try:
        return int(os.environ.get("OCR_TIMEOUT_SECONDS", 300))
    except (ValueError, TypeError):
        return 300


def get_max_edge_px() -> int:
    """Read max edge pixels from OCR_MAX_EDGE_PX env var, defaulting to 2200."""
    try:
        return int(os.environ.get("OCR_MAX_EDGE_PX", 2200))
    except (ValueError, TypeError):
        return 2200


def process_and_downscale_image(image_bytes: bytes, max_edge_px: int) -> tuple[bytes, list[int], list[int]]:
    """
    Open image using Pillow (detecting format by sniffing content).
    If max(width, height) exceeds max_edge_px, downscale preserving aspect ratio.
    Returns (processed_image_bytes, original_size, ocr_size).
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            orig_w, orig_h = img.size
            original_size = [orig_w, orig_h]
            longest_edge = max(orig_w, orig_h)

            if longest_edge > max_edge_px:
                scale = max_edge_px / float(longest_edge)
                new_w = max(1, int(round(orig_w * scale)))
                new_h = max(1, int(round(orig_h * scale)))

                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                ocr_size = [new_w, new_h]

                img_format = img.format or "JPEG"
                if img_format.upper() in ("JPEG", "JPG"):
                    if resized.mode in ("RGBA", "P", "LA"):
                        resized = resized.convert("RGB")

                out_buf = io.BytesIO()
                resized.save(out_buf, format=img_format)
                return out_buf.getvalue(), original_size, ocr_size
            else:
                return image_bytes, original_size, [orig_w, orig_h]
    except Exception as e:
        raise ValueError(f"Invalid or corrupt image format: {e}")


def run_tesseract(image_bytes: bytes, lang: str = "hin+eng", timeout: int | None = None) -> str:
    """
    Run Tesseract OCR on raw image bytes.
    Returns extracted text.
    Raises OCRTimeoutError on timeout, or OCRExecutionError on processing failure.
    """
    if not image_bytes or len(image_bytes) == 0:
        raise OCRExecutionError("Empty image data provided")

    if not LANG_PATTERN.match(lang):
        raise OCRExecutionError("Invalid language specification")

    if timeout is None:
        timeout = get_ocr_timeout()

    tmp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as f:
            f.write(image_bytes)
            tmp_file = f.name

        env = os.environ.copy()
        env["OMP_THREAD_LIMIT"] = "1"
        cmd = ["tesseract", tmp_file, "stdout", "-l", lang]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout,
            env=env,
        )

        if res.returncode != 0:
            raise OCRExecutionError("OCR processing failed: invalid or corrupt image format")

        text = res.stdout.strip()
        return text
    except subprocess.TimeoutExpired:
        raise OCRTimeoutError("OCR processing timed out")
    except (OCRTimeoutError, OCRExecutionError):
        raise
    except Exception:
        raise OCRExecutionError("Internal OCR execution error")
    finally:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "ocr-service"}), 200


@app.route("/ocr", methods=["POST"])
def ocr():
    lang = request.args.get("lang") or "hin+eng"
    image_bytes = None

    # 1. Handle multipart form file upload
    if "file" in request.files:
        uploaded = request.files["file"]
        image_bytes = uploaded.read()
        lang = request.form.get("lang", lang)
    elif "image" in request.files:
        uploaded = request.files["image"]
        image_bytes = uploaded.read()
        lang = request.form.get("lang", lang)
    # 2. Handle JSON payload (base64 image)
    elif request.is_json:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"error": "Invalid or non-JSON body"}), 400
        
        lang = data.get("lang", lang)
        b64_str = data.get("image") or data.get("image_base64")
        if not b64_str:
            return jsonify({"error": "Missing 'image' or 'image_base64' in JSON payload"}), 400

        # Strip data URI header if present
        if "," in b64_str and "base64" in b64_str.split(",")[0]:
            b64_str = b64_str.split(",", 1)[1]

        try:
            image_bytes = base64.b64decode(b64_str)
        except Exception:
            return jsonify({"error": "Invalid base64 encoding"}), 400
    # 3. Handle raw binary body
    elif request.data:
        image_bytes = request.data
    else:
        return jsonify({"error": "No image provided. Send multipart form (file/image) or JSON (image base64)"}), 400

    if not image_bytes:
        return jsonify({"error": "Empty or missing image data"}), 400

    max_edge_px = get_max_edge_px()
    try:
        ocr_bytes, original_size, ocr_size = process_and_downscale_image(image_bytes, max_edge_px)
    except ValueError:
        return jsonify({"error": "OCR processing failed: invalid or corrupt image format"}), 400

    timeout_sec = get_ocr_timeout()
    start_time = time.perf_counter()
    try:
        text = run_tesseract(ocr_bytes, lang=lang, timeout=timeout_sec)
    except OCRTimeoutError:
        return jsonify({"status": "timeout", "error": "OCR processing timed out"}), 504
    except OCRExecutionError as e:
        return jsonify({"error": str(e)}), 400

    duration_seconds = time.perf_counter() - start_time

    return jsonify({
        "status": "ok",
        "text": text,
        "char_count": len(text),
        "original_size": original_size,
        "ocr_size": ocr_size,
        "duration_seconds": round(duration_seconds, 3),
    }), 200


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tesseract OCR HTTP Service")
    parser.add_argument("--host", default=os.environ.get("HOST", "172.21.0.1"), help="Host to bind")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5050)), help="Port to bind")
    args = parser.parse_args()
    app.run(host=args.host, port=args.port)
