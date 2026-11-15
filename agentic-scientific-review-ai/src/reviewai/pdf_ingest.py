"""Bounded open-access PDF retrieval and page-labelled text extraction."""
from __future__ import annotations
import ipaddress
import re
import socket
from pathlib import Path
from urllib.parse import urlsplit
import requests
import fitz

MAX_BYTES = 12 * 1024 * 1024
MAX_PAGES = 50
MAX_CHARS = 80000


def _public_https_url(url: str) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    if parsed.port not in (None, 443):
        return False
    try:
        ips = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError):
        return False
    return bool(ips) and all(ipaddress.ip_address(x[4][0]).is_global for x in ips)


def extract_pdf(data: bytes) -> str:
    if len(data) > MAX_BYTES or not data.startswith(b"%PDF"):
        raise ValueError("PDF missing or larger than limit")
    pages = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for i in range(min(len(doc),MAX_PAGES)):
            pages.append(f"[PAGE {i+1}]\n" + doc[i].get_text("text"))
            if sum(map(len,pages)) >= MAX_CHARS:
                break
    return "\n".join(pages)[:MAX_CHARS]


def fetch_fulltext(paper: dict, timeout: int = 20, session=None) -> dict:
    """No redirects to avoid proxy/private-network SSRF. PDF failures are recorded, never hidden."""
    p = dict(paper)
    if p.get("full_text"):
        p["fulltext_status"] = "available"
        return p
    url = p.get("pdf_url") or ""
    if not url or not _public_https_url(url):
        p["fulltext_status"] = "not_retrieved"
        p["fulltext_error"] = "No allowed public HTTPS PDF URL"
        return p
    try:
        response = (session or requests).get(url, timeout=timeout, stream=True,
                                              allow_redirects=False,
                                              headers={"User-Agent":"AgenticReviewAI/0.1"})
        response.raise_for_status()
        if 300 <= response.status_code < 400:
            raise ValueError("Redirect blocked by download policy")
        content = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            content.extend(chunk)
            if len(content) > MAX_BYTES:
                raise ValueError("PDF exceeds 12 MiB limit")
        p["full_text"] = extract_pdf(bytes(content))
        if len(p["full_text"].strip()) < 100:
            raise ValueError("PDF did not contain sufficient extractable text")
        p["fulltext_status"] = "available"
        p["fulltext_error"] = ""
    except (requests.RequestException, ValueError, RuntimeError, fitz.FileDataError) as exc:
        p["full_text"] = ""
        p["fulltext_status"] = "not_retrieved"
        p["fulltext_error"] = str(exc)[:250]
    return p
