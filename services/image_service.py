"""Best-effort cover image generation via the free Pollinations.ai API."""

from __future__ import annotations

import urllib.parse
from typing import Any

from loguru import logger

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}?width=1280&height=720&model=flux&nologo=true&seed=42"


def generate_image_url(prompt: str) -> str | None:
    """Return a hosted image URL for a prompt, or None on any failure.

    Pollinations renders on demand and the returned URL is directly
    fetchable by publishing platforms, so no local download is needed.
    """
    if not prompt or not prompt.strip():
        return None
    url = POLLINATIONS_URL.format(prompt=urllib.parse.quote(prompt.strip()[:500]))
    logger.info("Requested cover image from Pollinations")
    return url
