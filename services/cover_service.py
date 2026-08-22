"""Cover image generation: HTML title card -> PNG -> free anonymous hosting.

Tries, in order: a repo logo (if the repo ships one) embedded in a styled
title card; otherwise a pure gradient title card. The PNG is uploaded to
Catbox (no API key) so publishing platforms can fetch it. Everything is
best-effort and never blocks publishing.
"""

from __future__ import annotations

import base64
import html
import re
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

from config import Config
from models.repository import RepositoryContext

CATBOX_API_URL = "https://catbox.moe/user/api.php"
LOGO_HINTS = ("logo", "favicon", "icon")
LOGO_EXTENSIONS = {".png", ".ico", ".svg", ".jpg", ".jpeg", ".webp", ".gif"}

IMAGE_MIME = {
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".svg": "image/svg+xml",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

CARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
@page {{ size: 1280px 720px; margin: 0; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ width: 1280px; height: 720px; font-family: 'DejaVu Sans', 'Segoe UI', system-ui, sans-serif; overflow: hidden; }}
.card {{ position: relative; width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: center; padding: 64px 84px; color: #ffffff; }}
.gradient {{ position: absolute; inset: 0; background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 48%, #7c3aed 100%); }}
.glow {{ position: absolute; width: 460px; height: 460px; border-radius: 50%; background: radial-gradient(circle, rgba(56, 189, 248, 0.35), transparent 70%); filter: blur(50px); }}
.glow.purple {{ background: radial-gradient(circle, rgba(167, 139, 250, 0.30), transparent 70%); }}
.content {{ position: relative; z-index: 2; }}
.logo-row {{ display: flex; align-items: center; gap: 18px; margin-bottom: 26px; }}
.logo-box {{ width: 76px; height: 76px; border-radius: 18px; background: rgba(255, 255, 255, 0.10); border: 1px solid rgba(255, 255, 255, 0.22); display: flex; align-items: center; justify-content: center; padding: 10px; }}
.logo-box img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
.kicker {{ font-size: 21px; letter-spacing: 4px; text-transform: uppercase; color: #7dd3fc; margin-bottom: 18px; font-weight: 600; }}
h1 {{ font-size: 56px; line-height: 1.14; font-weight: 800; max-width: 1080px; }}
.tags {{ display: flex; gap: 12px; margin-top: 30px; flex-wrap: wrap; }}
.tag {{ background: rgba(255, 255, 255, 0.12); border: 1px solid rgba(255, 255, 255, 0.28); border-radius: 999px; padding: 9px 22px; font-size: 18px; font-weight: 500; }}
.author {{ display: flex; align-items: center; gap: 14px; margin-top: 32px; }}
.avatar {{ width: 44px; height: 44px; border-radius: 9999px; background: linear-gradient(135deg, #38bdf8, #a78bfa); color: #0f172a; font-weight: 800; font-size: 20px; display: flex; align-items: center; justify-content: center; }}
.author-name {{ font-size: 19px; font-weight: 600; }}
.author-role {{ font-size: 15px; color: rgba(255, 255, 255, 0.6); margin-top: 2px; }}
.footer {{ position: absolute; bottom: 30px; left: 84px; font-size: 15px; color: rgba(255, 255, 255, 0.55); letter-spacing: 1px; }}
</style>
</head>
<body>
<div class="card">
  <div class="gradient"></div>
  <div class="glow" style="top: -140px; right: -120px;"></div>
  <div class="glow purple" style="bottom: -180px; left: -120px;"></div>
  <div class="content">
    {logo_row}
    <div class="kicker">Generated Article &middot; Repository Intelligence</div>
    <h1>{title}</h1>
    {tags_row}
    {author_row}
  </div>
  <div class="footer">generated with GitHub Doc AI</div>
</div>
</body>
</html>"""


def find_repo_logo(context: RepositoryContext) -> str | None:
    """Return the local path of a repo logo/favicon if the repo ships one.

    Scans the clone on disk (the parser skips binary files, so the logo is
    not present in ``context.files``).
    """
    clone_root = context.clone_path
    if not clone_root:
        return None
    excluded_dirs = {"node_modules", "dist", "build", ".git", ".next", "coverage", "vendor"}
    candidates: list[tuple[str, int]] = []
    for directory, dirnames, filenames in Path(clone_root).walk(on_error=lambda _: None):
        dirnames[:] = [d for d in dirnames if d not in excluded_dirs]
        for filename in filenames:
            lowered = filename.lower()
            extension = Path(filename).suffix.lower()
            if extension not in LOGO_EXTENSIONS:
                continue
            if not any(hint in lowered for hint in LOGO_HINTS):
                continue
            full_path = Path(directory) / filename
            try:
                size = full_path.stat().st_size
            except OSError:
                continue
            candidates.append((str(full_path), size))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0].endswith(".ico"), -item[1]))
    return candidates[0][0]


def build_title_card_html(
    title: str,
    subtitle: str = "",
    tags: list[str] | None = None,
    logo_bytes: bytes | None = None,
    logo_mime: str = "image/png",
    author: str = "",
) -> str:
    """Render a styled 1280x720 title-card HTML document for the title."""
    logo_row = ""
    if logo_bytes:
        data_uri = f"data:{logo_mime};base64,{base64.b64encode(logo_bytes).decode('ascii')}"
        logo_row = f'<div class="logo-row"><div class="logo-box"><img src="{data_uri}" alt="logo"></div></div>'

    safe_title = html.escape(title or "Generated Content")
    tag_pills = "".join(
        f'<span class="tag">{html.escape(str(tag))}</span>' for tag in (tags or [])[:4]
    )
    tags_row = f'<div class="tags">{tag_pills}</div>' if tag_pills else ""

    author_row = ""
    if author and author.strip():
        safe_author = html.escape(author.strip())
        initial = html.escape(author.strip()[0].upper())
        author_row = (
            '<div class="author">'
            f'<div class="avatar">{initial}</div>'
            "<div>"
            f'<div class="author-name">{safe_author}</div>'
            '<div class="author-role">Author &middot; GitHub</div>'
            "</div>"
            "</div>"
        )

    return CARD_HTML.format(
        logo_row=logo_row,
        title=safe_title,
        tags_row=tags_row,
        author_row=author_row,
    )


def render_title_card_png(html_document: str) -> bytes | None:
    """Render the title-card HTML to PNG bytes.

    WeasyPrint only outputs PDF, so the result is converted to a single-page
    PNG with poppler's pdftoppm when available.
    """
    import subprocess
    import tempfile

    try:
        from weasyprint import HTML
    except ImportError:
        logger.warning("WeasyPrint unavailable; cannot render title card")
        return None
    try:
        pdf_bytes = HTML(string=html_document).write_pdf()
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "card.pdf"
            png_path = Path(tmp) / "card.png"
            pdf_path.write_bytes(pdf_bytes)
            result = subprocess.run(
                ["pdftoppm", "-png", "-singlefile", "-r", "96", str(pdf_path), str(Path(tmp) / "card")],
                capture_output=True,
                timeout=60,
            )
            if result.returncode != 0 or not png_path.exists():
                logger.warning("pdftoppm conversion failed: {}", result.stderr.decode(errors="replace")[:200])
                return None
            return png_path.read_bytes()
    except Exception as exc:  # noqa: BLE001 - cover images are best-effort
        logger.warning("Title card render failed: {}", exc)
        return None


def upload_to_catbox(image_bytes: bytes, filename: str = "cover.png") -> str | None:
    """Upload PNG bytes to Catbox (anonymous) and return the public URL."""
    boundary = "----FormBoundary" + uuid.uuid4().hex
    def field(name: str) -> bytes:
        return (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n"
        ).encode("utf-8")

    body = bytearray()
    body += field("reqtype") + b"fileupload\r\n"
    body += (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="fileToUpload"; filename="{filename}"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode("utf-8")
    body += image_bytes
    body += f"\r\n--{boundary}--\r\n".encode("utf-8")

    request = urllib.request.Request(
        CATBOX_API_URL,
        data=bytes(body),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        },
        method="POST",
    )
    url = ""
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                url = response.read().decode("utf-8", errors="replace").strip()
            break
        except Exception as exc:  # noqa: BLE001 - retry transient network failures
            last_error = exc
            logger.warning("Catbox upload failed on attempt {}: {}", attempt + 1, exc)
            if attempt < 2:
                time.sleep(min(2 ** attempt, 8))
    if not url:
        if last_error:
            logger.warning("Catbox upload failed after retries: {}", last_error)
        else:
            logger.warning("Catbox returned an unexpected empty response")
        return None
    if not url.startswith("http"):
        logger.warning("Catbox returned an unexpected response: {}", url[:120])
        return None
    logger.info("Uploaded title card to {}", url)
    return url


def read_logo_file(path: str | None) -> tuple[bytes | None, str]:
    """Read a logo file from disk; returns (bytes, mime)."""
    if not path:
        return None, "image/png"
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None, "image/png"
    if not data:
        return None, "image/png"
    mime = IMAGE_MIME.get(Path(path).suffix.lower(), "image/png")
    return data, mime
