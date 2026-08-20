#!/usr/bin/env python3
"""
ACTION-002: Newspaper Sweep Runner (Recruitment-day map)

Sweeps newspaper editions to map which weekdays carry recruitment classifieds
and appointments, and on which page numbers.
"""

import os
import re
import sys
import time
import sqlite3
import argparse
import datetime
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from PIL import Image

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Referer": "https://www.indupaper.com/",
}


# Per-paper recruitment days. Measured as qualified leads per edition-day,
# not keyword density: keyword-dense pages are often matrimonial. See
# RECRUITMENT-DAY-MAP.md. HT peaks Tuesday and is a near-zero Wednesday,
# the opposite of TOI and Mirror.
EDITIONS = [
    {
        "key": "toi-ahmedabad",
        "paper": "Times of India",
        "city": "ahmedabad",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/toi/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "ahmedabad"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "toi-bangalore",
        "paper": "Times of India",
        "city": "bangalore",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/toi/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "bangalore"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "toi-bhopal",
        "paper": "Times of India",
        "city": "bhopal",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/toi/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "bhopal"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "toi-chandigarh",
        "paper": "Times of India",
        "city": "chandigarh",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/toi/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "chandigarh"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "toi-chennai",
        "paper": "Times of India",
        "city": "chennai",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/toi/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "chennai"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "toi-delhi",
        "paper": "Times of India",
        "city": "delhi",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/toi/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "delhi"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "toi-goa",
        "paper": "Times of India",
        "city": "goa",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/toi/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "goa"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "toi-hyderabad",
        "paper": "Times of India",
        "city": "hyderabad",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/toi/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "hyderabad"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "toi-jaipur",
        "paper": "Times of India",
        "city": "jaipur",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/toi/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "jaipur"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "toi-kochi",
        "paper": "Times of India",
        "city": "kochi",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/toi/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "kochi"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "toi-kolkata",
        "paper": "Times of India",
        "city": "kolkata",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/toi/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "kolkata"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "toi-lucknow",
        "paper": "Times of India",
        "city": "lucknow",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/toi/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "lucknow"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "toi-mumbai",
        "paper": "Times of India",
        "city": "mumbai",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/toi/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "mumbai"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "toi-pune",
        "paper": "Times of India",
        "city": "pune",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/toi/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "pune"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "mirror-bangalore",
        "paper": "Mirror",
        "city": "bangalore",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/mirror/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "bangalore"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "mirror-mumbai",
        "paper": "Mirror",
        "city": "mumbai",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/mirror/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "mumbai"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "mirror-pune",
        "paper": "Mirror",
        "city": "pune",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/mirror/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "pune"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "et-bangalore",
        "paper": "Economic Times",
        "city": "bangalore",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/economictimes/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "bangalore"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "et-delhi",
        "paper": "Economic Times",
        "city": "delhi",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/economictimes/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "delhi"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "et-kolkata",
        "paper": "Economic Times",
        "city": "kolkata",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/economictimes/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "kolkata"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "et-mumbai",
        "paper": "Economic Times",
        "city": "mumbai",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/economictimes/v2/download",
        "date_style": "dmy",
        "params": {"citySlug": "mumbai"},
        "days": ["Wednesday", "Sunday"],
    },
    {
        "key": "ht-chandigarh",
        "paper": "Hindustan Times",
        "city": "chandigarh",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/hindustantimes/v2/download",
        "date_style": "iso",
        "params": {"citySlug": "chandigarh"},
        "days": ["Tuesday", "Sunday"],
    },
    {
        "key": "ht-delhi",
        "paper": "Hindustan Times",
        "city": "delhi",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/hindustantimes/v2/download",
        "date_style": "iso",
        "params": {"citySlug": "delhi"},
        "days": ["Tuesday", "Sunday"],
    },
    {
        "key": "ht-gurgaon",
        "paper": "Hindustan Times",
        "city": "gurgaon",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/hindustantimes/v2/download",
        "date_style": "iso",
        "params": {"citySlug": "gurgaon"},
        "days": ["Tuesday", "Sunday"],
    },
    {
        "key": "ht-lucknow",
        "paper": "Hindustan Times",
        "city": "lucknow",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/hindustantimes/v2/download",
        "date_style": "iso",
        "params": {"citySlug": "lucknow"},
        "days": ["Tuesday", "Sunday"],
    },
    {
        "key": "ht-mumbai",
        "paper": "Hindustan Times",
        "city": "mumbai",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/hindustantimes/v2/download",
        "date_style": "iso",
        "params": {"citySlug": "mumbai"},
        "days": ["Tuesday", "Sunday"],
    },
    {
        "key": "ht-noida",
        "paper": "Hindustan Times",
        "city": "noida",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/hindustantimes/v2/download",
        "date_style": "iso",
        "params": {"citySlug": "noida"},
        "days": ["Tuesday", "Sunday"],
    },
    {
        "key": "ht-patna",
        "paper": "Hindustan Times",
        "city": "patna",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/hindustantimes/v2/download",
        "date_style": "iso",
        "params": {"citySlug": "patna"},
        "days": ["Tuesday", "Sunday"],
    },
    {
        "key": "ht-pune",
        "paper": "Hindustan Times",
        "city": "pune",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/hindustantimes/v2/download",
        "date_style": "iso",
        "params": {"citySlug": "pune"},
        "days": ["Tuesday", "Sunday"],
    },
    {
        "key": "ht-ranchi",
        "paper": "Hindustan Times",
        "city": "ranchi",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/hindustantimes/v2/download",
        "date_style": "iso",
        "params": {"citySlug": "ranchi"},
        "days": ["Tuesday", "Sunday"],
    },
    {
        "key": "ht-thane",
        "paper": "Hindustan Times",
        "city": "thane",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/hindustantimes/v2/download",
        "date_style": "iso",
        "params": {"citySlug": "thane"},
        "days": ["Tuesday", "Sunday"],
    },
    {
        "key": "ht-varanasi",
        "paper": "Hindustan Times",
        "city": "varanasi",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/hindustantimes/v2/download",
        "date_style": "iso",
        "params": {"citySlug": "varanasi"},
        "days": ["Tuesday", "Sunday"],
    },
    {
        "key": "excelsior-jammu",
        "paper": "Daily Excelsior",
        "city": "jammu",
        "url": "https://d1h47qec6ptx2j.cloudfront.net/dailyexcelsior/v1/download",
        "date_style": "ddmmyyyy_slash",
        "params": {"editionid": "1"},
        "days": ["Tuesday", "Wednesday", "Sunday"],
    },
]

KEYWORDS = [
    "vacancy", "vacancies", "vacant", "required", "requires", "wanted", "hiring",
    "walk-in", "walkin", "recruitment", "appointment", "appointments", "resume",
    "curriculum vitae", "situations vacant", "apply now", "send cv", "candidates",
    "applications invited", "post of", "salary"
]

KEYWORD_PATTERNS = [re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE) for kw in KEYWORDS]
PHONE_RE = re.compile(r"[6-9][0-9]{9}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
IMG_SRC_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)


def count_keywords(text: str) -> int:
    if not text:
        return 0
    total = 0
    for pattern in KEYWORD_PATTERNS:
        total += len(pattern.findall(text))
    return total


def init_db(db_path: str):
    db_dir = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(db_dir, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS manifest (
                edition_key TEXT NOT NULL,
                edition_date TEXT NOT NULL,
                weekday TEXT NOT NULL,
                page_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (edition_key, edition_date)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS page_scan (
                edition_key TEXT NOT NULL,
                paper TEXT NOT NULL,
                city TEXT NOT NULL,
                edition_date TEXT NOT NULL,
                weekday TEXT NOT NULL,
                page_no INTEGER NOT NULL,
                image_url TEXT NOT NULL,
                image_bytes INTEGER,
                ocr_chars INTEGER,
                keyword_count INTEGER,
                phone_count INTEGER,
                email_count INTEGER,
                full_text TEXT,
                pass1_seconds REAL,
                pass2_seconds REAL,
                status TEXT NOT NULL,
                error TEXT,
                scanned_at TEXT NOT NULL,
                PRIMARY KEY (edition_key, edition_date, page_no)
            )
            """
        )
        conn.commit()


def get_existing_page_status(db_path: str, edition_key: str, date_str: str, page_no: int) -> str | None:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status FROM page_scan WHERE edition_key = ? AND edition_date = ? AND page_no = ?",
            (edition_key, date_str, page_no),
        )
        row = cursor.fetchone()
        return row[0] if row else None


def save_manifest(db_path: str, edition_key: str, date_str: str, weekday: str, page_count: int, status: str, error: str | None):
    fetched_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO manifest (edition_key, edition_date, weekday, page_count, status, error, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(edition_key, edition_date) DO UPDATE SET
                weekday=excluded.weekday,
                page_count=excluded.page_count,
                status=excluded.status,
                error=excluded.error,
                fetched_at=excluded.fetched_at
            """,
            (edition_key, date_str, weekday, page_count, status, error, fetched_at),
        )
        conn.commit()


def save_page_scan(db_path: str, db_lock: threading.Lock, row: dict):
    with db_lock:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO page_scan (
                    edition_key, paper, city, edition_date, weekday, page_no, image_url,
                    image_bytes, ocr_chars, keyword_count, phone_count, email_count,
                    full_text, pass1_seconds, pass2_seconds, status, error, scanned_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(edition_key, edition_date, page_no) DO UPDATE SET
                    paper=excluded.paper,
                    city=excluded.city,
                    weekday=excluded.weekday,
                    image_url=excluded.image_url,
                    image_bytes=excluded.image_bytes,
                    ocr_chars=excluded.ocr_chars,
                    keyword_count=excluded.keyword_count,
                    phone_count=excluded.phone_count,
                    email_count=excluded.email_count,
                    full_text=excluded.full_text,
                    pass1_seconds=excluded.pass1_seconds,
                    pass2_seconds=excluded.pass2_seconds,
                    status=excluded.status,
                    error=excluded.error,
                    scanned_at=excluded.scanned_at
                """,
                (
                    row["edition_key"], row["paper"], row["city"], row["edition_date"],
                    row["weekday"], row["page_no"], row["image_url"], row["image_bytes"],
                    row["ocr_chars"], row["keyword_count"], row["phone_count"],
                    row["email_count"], row["full_text"], row["pass1_seconds"],
                    row["pass2_seconds"], row["status"], row["error"], row["scanned_at"]
                ),
            )
            conn.commit()


def update_page_scan_pass2(
    db_path: str,
    db_lock: threading.Lock,
    edition_key: str,
    date_str: str,
    page_no: int,
    phone_count: int | None,
    email_count: int | None,
    full_text: str | None,
    pass2_seconds: float | None,
    status: str,
    error: str | None,
):
    with db_lock:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE page_scan
                SET phone_count = ?,
                    email_count = ?,
                    full_text = ?,
                    pass2_seconds = ?,
                    status = ?,
                    error = ?
                WHERE edition_key = ? AND edition_date = ? AND page_no = ?
                """,
                (phone_count, email_count, full_text, pass2_seconds, status, error, edition_key, date_str, page_no),
            )
            conn.commit()


def repass2_page(row: tuple, args, db_lock: threading.Lock) -> dict:
    edition_key, date_str, page_no, image_url = row
    temp_orig = None
    phone_count = None
    email_count = None
    full_text = None
    pass2_seconds = None
    status = "ok"
    error = None

    try:
        r = requests.get(image_url, headers=HTTP_HEADERS, stream=True, timeout=60)
        if r.status_code != 200:
            status = "download_failed"
            error = f"HTTP {r.status_code}"
            return {"status": status}

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f_orig:
            temp_orig = f_orig.name
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f_orig.write(chunk)

        if os.path.getsize(temp_orig) == 0:
            status = "download_failed"
            error = "Empty file downloaded"
            return {"status": status}

        t0_p2 = time.perf_counter()
        with open(temp_orig, "rb") as f_p2:
            res2 = requests.post("http://172.21.0.1:5050/ocr?lang=eng&max_edge=0", files={"file": f_p2}, timeout=360)
        pass2_seconds = round(time.perf_counter() - t0_p2, 3)

        if res2.status_code == 504:
            status = "timeout"
            error = "Pass 2 OCR timed out"
            return {"status": status}
        elif res2.status_code != 200:
            status = "ocr_failed"
            error = f"Pass 2 OCR HTTP {res2.status_code}: {res2.text[:200]}"
            return {"status": status}

        p2_json = res2.json()
        orig_sz = p2_json.get("original_size")
        ocr_sz = p2_json.get("ocr_size")
        if not orig_sz or not ocr_sz or orig_sz != ocr_sz:
            status = "ocr_failed"
            error = f"Pass 2 was downscaled: original_size={orig_sz}, ocr_size={ocr_sz}"
            return {"status": status}

        full_text = p2_json.get("text", "")
        phone_count = len(PHONE_RE.findall(full_text))
        email_count = len(EMAIL_RE.findall(full_text))

    except requests.Timeout:
        status = "timeout"
        error = "Pass 2 OCR timed out"
    except Exception as e:
        status = "ocr_failed"
        error = f"Pass 2 error: {e}"
    finally:
        if temp_orig and os.path.exists(temp_orig):
            try:
                os.remove(temp_orig)
            except OSError:
                pass

        update_page_scan_pass2(
            args.db,
            db_lock,
            edition_key,
            date_str,
            page_no,
            phone_count,
            email_count,
            full_text,
            pass2_seconds,
            status,
            error,
        )

        phones_str = str(phone_count) if phone_count is not None else "-"
        emails_str = str(email_count) if email_count is not None else "-"
        p2_sec_str = f"{pass2_seconds:.1f}s" if pass2_seconds is not None else "-"
        print(
            f"[repass2] {edition_key} {date_str} p{page_no:02d} phones={phones_str} emails={emails_str} {p2_sec_str} {status}",
            flush=True,
        )

    return {"status": status}


def process_page(edition: dict, date_obj: datetime.date, weekday: str, page_no: int, image_url: str, args, db_lock: threading.Lock) -> dict:
    edition_key = edition["key"]
    paper = edition["paper"]
    city = edition["city"]
    date_str = date_obj.strftime("%Y-%m-%d")

    t_start = time.perf_counter()
    temp_orig = None
    temp_downscaled = None

    image_bytes = None
    ocr_chars = None
    keyword_count = None
    phone_count = None
    email_count = None
    full_text = None
    pass1_seconds = None
    pass2_seconds = None
    status = "ok"
    error = None

    try:
        # Stream download directly to temp file
        try:
            r = requests.get(image_url, headers=HTTP_HEADERS, stream=True, timeout=60)
            if r.status_code != 200:
                status = "download_failed"
                error = f"HTTP {r.status_code}"
                return {"status": status}

            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f_orig:
                temp_orig = f_orig.name
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f_orig.write(chunk)

            image_bytes = os.path.getsize(temp_orig)
            if image_bytes == 0:
                status = "download_failed"
                error = "Empty file downloaded"
                return {"status": status}
        except Exception as e:
            status = "download_failed"
            error = f"Download error: {e}"
            return {"status": status}

        # Pass 1: Downscale image using Pillow and close immediately
        try:
            with Image.open(temp_orig) as img:
                orig_w, orig_h = img.size
                longest_edge = max(orig_w, orig_h)
                if longest_edge > args.max_edge:
                    scale = args.max_edge / float(longest_edge)
                    new_w = max(1, int(round(orig_w * scale)))
                    new_h = max(1, int(round(orig_h * scale)))
                    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    if resized.mode in ("RGBA", "P", "LA"):
                        resized = resized.convert("RGB")
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f_down:
                        temp_downscaled = f_down.name
                        resized.save(f_down, format="JPEG", quality=85)
                    resized.close()
                else:
                    temp_downscaled = None
        except MemoryError as me:
            status = "ocr_failed"
            error = f"MemoryError downscaling: {me}"
            return {"status": status}
        except Exception as e:
            status = "ocr_failed"
            error = f"Downscale error: {e}"
            return {"status": status}

        pass1_file = temp_downscaled if temp_downscaled else temp_orig

        # Pass 1 OCR
        try:
            t0_p1 = time.perf_counter()
            with open(pass1_file, "rb") as f_p1:
                res1 = requests.post(f"http://172.21.0.1:5050/ocr?lang=eng&max_edge={args.max_edge}", files={"file": f_p1}, timeout=360)
            pass1_seconds = round(time.perf_counter() - t0_p1, 3)

            if res1.status_code == 504:
                status = "timeout"
                error = "OCR processing timed out"
                return {"status": status}
            elif res1.status_code != 200:
                status = "ocr_failed"
                error = f"OCR HTTP {res1.status_code}: {res1.text[:200]}"
                return {"status": status}

            p1_json = res1.json()
            pass1_text = p1_json.get("text", "")
            ocr_chars = len(pass1_text)
            keyword_count = count_keywords(pass1_text)
        except requests.Timeout:
            status = "timeout"
            error = "OCR request timed out"
            return {"status": status}
        except Exception as e:
            status = "ocr_failed"
            error = f"Pass 1 OCR error: {e}"
            return {"status": status}

        # Pass 2: If keyword_count >= threshold, OCR original full-res image
        if keyword_count >= args.keyword_threshold:
            try:
                t0_p2 = time.perf_counter()
                with open(temp_orig, "rb") as f_p2:
                    res2 = requests.post("http://172.21.0.1:5050/ocr?lang=eng&max_edge=0", files={"file": f_p2}, timeout=360)
                pass2_seconds = round(time.perf_counter() - t0_p2, 3)

                if res2.status_code == 504:
                    status = "timeout"
                    error = "Pass 2 OCR timed out"
                    return {"status": status}
                elif res2.status_code != 200:
                    status = "ocr_failed"
                    error = f"Pass 2 OCR HTTP {res2.status_code}: {res2.text[:200]}"
                    return {"status": status}

                p2_json = res2.json()
                orig_sz = p2_json.get("original_size")
                ocr_sz = p2_json.get("ocr_size")
                if not orig_sz or not ocr_sz or orig_sz != ocr_sz:
                    status = "ocr_failed"
                    error = f"Pass 2 was downscaled: original_size={orig_sz}, ocr_size={ocr_sz}"
                    return {"status": status}

                full_text = p2_json.get("text", "")
                phone_count = len(PHONE_RE.findall(full_text))
                email_count = len(EMAIL_RE.findall(full_text))
            except requests.Timeout:
                status = "timeout"
                error = "Pass 2 OCR timed out"
                return {"status": status}
            except Exception as e:
                status = "ocr_failed"
                error = f"Pass 2 OCR error: {e}"
                return {"status": status}

    except MemoryError as me:
        status = "ocr_failed"
        error = f"MemoryError: {me}"
    except Exception as e:
        status = "ocr_failed"
        error = f"Unexpected error: {e}"
    finally:
        # Delete temp files in finally block
        if temp_downscaled and os.path.exists(temp_downscaled):
            try:
                os.remove(temp_downscaled)
            except OSError:
                pass
        if temp_orig and os.path.exists(temp_orig):
            try:
                os.remove(temp_orig)
            except OSError:
                pass

        total_secs = time.perf_counter() - t_start
        scanned_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        row = {
            "edition_key": edition_key,
            "paper": paper,
            "city": city,
            "edition_date": date_str,
            "weekday": weekday,
            "page_no": page_no,
            "image_url": image_url,
            "image_bytes": image_bytes,
            "ocr_chars": ocr_chars,
            "keyword_count": keyword_count,
            "phone_count": phone_count,
            "email_count": email_count,
            "full_text": full_text,
            "pass1_seconds": pass1_seconds,
            "pass2_seconds": pass2_seconds,
            "status": status,
            "error": error,
            "scanned_at": scanned_at,
        }

        save_page_scan(args.db, db_lock, row)

        # Format output line
        kw_str = str(keyword_count) if keyword_count is not None else "-"
        chars_str = str(ocr_chars) if ocr_chars is not None else "-"
        bytes_val = image_bytes if image_bytes is not None else 0
        if phone_count is not None and email_count is not None:
            extra = f"phones={phone_count} emails={email_count} "
        else:
            extra = ""

        print(
            f"{edition_key} {date_str} {weekday} p{page_no:02d} bytes={bytes_val} kw={kw_str} chars={chars_str} {extra}{total_secs:.1f}s {status}",
            flush=True,
        )

    return {"status": status}


def check_manifest_stub(img_urls: list[str]) -> tuple[bool, str | None]:
    if not img_urls:
        return False, None
    for u in img_urls:
        if "indupaper.com/assets/" in u:
            return True, f"Image URL contains indupaper.com/assets/: {u}"
    if len(img_urls) <= 5:
        sizes = []
        for u in img_urls:
            try:
                head_res = requests.head(u, headers=HTTP_HEADERS, timeout=10, allow_redirects=True)
                cl = head_res.headers.get("content-length")
                if head_res.status_code == 200 and cl is not None and cl.isdigit():
                    sizes.append(int(cl))
                else:
                    get_res = requests.get(u, headers=HTTP_HEADERS, stream=True, timeout=10)
                    cl = get_res.headers.get("content-length")
                    if cl is not None and cl.isdigit():
                        sizes.append(int(cl))
                    else:
                        sizes.append(len(get_res.content))
            except Exception:
                pass
        if sizes:
            avg_size = sum(sizes) / len(sizes)
            if avg_size < 200 * 1024:
                return True, f"Stub detected: {len(img_urls)} pages with average size {avg_size/1024:.1f}KB (<200KB)"
    return False, None


def fetch_manifest(edition: dict, date_obj: datetime.date) -> tuple[list[str], str, str | None]:
    date_style = edition.get("date_style", "iso")
    params = dict(edition.get("params", {}))
    if date_style == "iso":
        params["editionDate"] = date_obj.strftime("%Y-%m-%d")
    elif date_style == "dmy":
        params["day"] = f"{date_obj.day:02d}"
        params["month"] = f"{date_obj.month:02d}"
        params["year"] = f"{date_obj.year:04d}"
    elif date_style == "ddmmyyyy_slash":
        params["editiondate"] = date_obj.strftime("%d/%m/%Y")

    try:
        res = requests.get(edition["url"], params=params, headers=HTTP_HEADERS, timeout=30)
        if res.status_code != 200:
            return [], "fetch_failed", f"HTTP {res.status_code}"
        data = res.json()
        html = ""
        if isinstance(data.get("data"), dict):
            html = data["data"].get("htmlContent", "")
        img_urls = IMG_SRC_RE.findall(html)
        if not img_urls:
            return [], "empty", "No images found in manifest"

        is_stub, stub_reason = check_manifest_stub(img_urls)
        if is_stub:
            return img_urls, "manifest_stub", stub_reason

        return img_urls, "ok", None
    except Exception as e:
        return [], "fetch_failed", str(e)


def main():
    parser = argparse.ArgumentParser(description="Newspaper Sweep Runner (Recruitment-day map)")
    parser.add_argument("--days", type=int, default=56, help="Number of days to sweep backwards from today-1")
    parser.add_argument("--editions", type=str, default="all", help="Comma-separated edition keys or 'all'")
    parser.add_argument("--max-edge", type=int, default=2200, help="Max edge in pixels for pass 1 downscaling")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent page workers")
    parser.add_argument("--keyword-threshold", type=int, default=8, help="Keyword count threshold to trigger pass 2")
    parser.add_argument("--repass2", action="store_true", help="Re-run pass 2 only on existing rows with keyword_count >= threshold")
    parser.add_argument("--ignore-day-map", action="store_true", help="Sweep every edition regardless of its per-paper recruitment days")
    parser.add_argument("--db", type=str, default="/root/newspaper_sweep/sweep.db", help="Path to SQLite database")
    args = parser.parse_args()

    init_db(args.db)
    db_lock = threading.Lock()

    if args.editions.lower() == "all":
        selected_editions = EDITIONS
    else:
        req_keys = [k.strip() for k in args.editions.split(",") if k.strip()]
        selected_editions = [e for e in EDITIONS if e["key"] in req_keys]
        if not selected_editions:
            print(f"Error: No matching editions found for: {args.editions}", file=sys.stderr)
            sys.exit(1)

    if args.repass2:
        query = "SELECT edition_key, edition_date, page_no, image_url FROM page_scan WHERE keyword_count >= ?"
        params = [args.keyword_threshold]
        if args.editions.lower() != "all":
            placeholders = ",".join("?" for _ in selected_editions)
            query += f" AND edition_key IN ({placeholders})"
            params.extend([e["key"] for e in selected_editions])
        query += " ORDER BY edition_date DESC, edition_key, page_no"

        with sqlite3.connect(args.db) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        print(f"Found {len(rows)} pages with keyword_count >= {args.keyword_threshold} to re-process pass 2")
        if not rows:
            return

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [
                executor.submit(
                    repass2_page,
                    row_data,
                    args,
                    db_lock,
                )
                for row_data in rows
            ]
            for fut in as_completed(futures):
                try:
                    fut.result()
                except Exception as e:
                    print(f"Error in repass2 task: {e}", file=sys.stderr)
        return

    today = datetime.date.today()
    dates = [today - datetime.timedelta(days=i) for i in range(1, args.days + 1)]

    for date_obj in dates:
        date_str = date_obj.strftime("%Y-%m-%d")
        weekday = date_obj.strftime("%A")

        for edition in selected_editions:
            edition_key = edition["key"]

            # Per-paper recruitment-day gate. Skip an edition on a weekday it
            # does not carry classifieds, rather than paying OCR to find out.
            ed_days = edition.get("days")
            if ed_days and weekday not in ed_days and not args.ignore_day_map:
                print(
                    f"Skip {edition_key} {date_str} ({weekday}): not a recruitment day for this paper",
                    flush=True,
                )
                continue

            t_ed_start = time.perf_counter()

            # Manifest request
            img_urls, manifest_status, manifest_error = fetch_manifest(edition, date_obj)
            save_manifest(args.db, edition_key, date_str, weekday, len(img_urls), manifest_status, manifest_error)
            time.sleep(0.5)

            if manifest_status != "ok" or not img_urls:
                total_ed_secs = time.perf_counter() - t_ed_start
                print(
                    f"Summary {edition_key} {date_str} ({weekday}): 0 pages (0 ok, 0 timeout, 0 failed) in {total_ed_secs:.1f}s",
                    flush=True,
                )
                continue

            pages_to_scan = []
            for idx, img_url in enumerate(img_urls, start=1):
                existing_status = get_existing_page_status(args.db, edition_key, date_str, idx)
                if existing_status == "ok":
                    continue
                pages_to_scan.append((idx, img_url))

            counts = {"ok": len(img_urls) - len(pages_to_scan), "timeout": 0, "failed": 0}

            if pages_to_scan:
                with ThreadPoolExecutor(max_workers=args.workers) as executor:
                    futures = [
                        executor.submit(
                            process_page,
                            edition,
                            date_obj,
                            weekday,
                            page_no,
                            img_url,
                            args,
                            db_lock,
                        )
                        for page_no, img_url in pages_to_scan
                    ]
                    for fut in as_completed(futures):
                        try:
                            res = fut.result()
                            st = res.get("status", "failed")
                            if st == "ok":
                                counts["ok"] += 1
                            elif st == "timeout":
                                counts["timeout"] += 1
                            else:
                                counts["failed"] += 1
                        except Exception:
                            counts["failed"] += 1

            total_ed_secs = time.perf_counter() - t_ed_start
            print(
                f"Summary {edition_key} {date_str} ({weekday}): {len(img_urls)} pages ({counts['ok']} ok, {counts['timeout']} timeout, {counts['failed']} failed) in {total_ed_secs:.1f}s",
                flush=True,
            )


if __name__ == "__main__":
    main()
