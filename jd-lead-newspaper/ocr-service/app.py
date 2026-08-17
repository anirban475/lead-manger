#!/usr/bin/env python3
"""
Tesseract OCR HTTP Service
Provides a lightweight HTTP wrapper around Tesseract OCR for n8n workflows.
Exposes POST /ocr accepting multipart file upload or base64 encoded JSON.
Binds to 172.21.0.1:5050 (docker bridge gateway for amatec-net).
"""

import os
import re
import base64
import tempfile
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)

# Max payload size: 32MB
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

LANG_PATTERN = re.compile(r"^[a-zA-Z0-9+_]+$")


def run_tesseract(image_bytes: bytes, lang: str = "hin+eng") -> tuple[str | None, str | None]:
    """
    Run Tesseract OCR on raw image bytes.
    Returns (extracted_text, error_message).
    """
    if not image_bytes or len(image_bytes) == 0:
        return None, "Empty image data provided"

    if not LANG_PATTERN.match(lang):
        return None, "Invalid language specification"

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
            timeout=60,
            env=env,
        )

        if res.returncode != 0:
            return None, "OCR processing failed: invalid or corrupt image format"

        text = res.stdout.strip()
        return text, None
    except subprocess.TimeoutExpired:
        return None, "OCR processing timed out"
    except Exception:
        return None, "Internal OCR execution error"
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

    text, error = run_tesseract(image_bytes, lang=lang)
    if error:
        return jsonify({"error": error}), 400

    return jsonify({"text": text, "char_count": len(text)}), 200


if __name__ == "__main__":
    host = os.environ.get("HOST", "172.21.0.1")
    port = int(os.environ.get("PORT", 5050))
    app.run(host=host, port=port)
