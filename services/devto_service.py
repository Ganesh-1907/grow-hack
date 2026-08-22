"""Dev.to publishing service for generated content."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from loguru import logger

from config import Config

DEVTO_API_URL = "https://dev.to/api/articles"


class DevToError(Exception):
    """Raised when publishing to Dev.to fails."""


class DevToService:
    """Publish generated content to the Forem (Dev.to) API."""

    def __init__(self, config: Config) -> None:
        """Create the service with injected configuration."""
        self.config = config

    def is_configured(self) -> bool:
        """Return whether a Dev.to API key is available."""
        return bool(self.config.devto_api_key)

    def publish(
        self,
        title: str,
        body_markdown: str,
        tags: list[str] | None = None,
        published: bool = True,
        main_image: str | None = None,
    ) -> dict[str, Any]:
        """Publish an article and return the live URL from Dev.to.

        Args:
            title: Article title.
            body_markdown: Article body in Markdown.
            tags: Up to 4 Dev.to-compatible tags.
            published: Whether to publish immediately (True) or save as a draft.
            main_image: Optional cover image URL.

        Returns:
            Dict containing the live article ``url``.

        Raises:
            DevToError: If the request fails or Dev.to returns an error.
        """
        if not self.is_configured():
            raise DevToError("Dev.to API key is not configured.")

        article: dict[str, Any] = {
            "title": title,
            "body_markdown": body_markdown,
            "published": published,
            "tags": (tags or [])[:4],
        }
        if main_image:
            article["main_image"] = main_image

        payload = json.dumps({"article": article}).encode("utf-8")
        request = urllib.request.Request(
            DEVTO_API_URL,
            data=payload,
            headers={
                "api-key": self.config.devto_api_key,
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            },
            method="POST",
        )

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=self.config.llm_timeout_seconds) as response:
                    data = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code < 500:
                    detail = exc.read().decode("utf-8", errors="replace")[:300]
                    raise DevToError(f"Dev.to API returned {exc.code}: {detail}") from exc
                logger.warning("Dev.to API returned {} on attempt {}", exc.code, attempt + 1)
            except urllib.error.URLError as exc:
                last_error = exc
                logger.warning("Dev.to API unreachable on attempt {}: {}", attempt + 1, exc.reason)
            except (json.JSONDecodeError, TypeError) as exc:
                raise DevToError(f"Dev.to returned an unreadable response: {exc}") from exc
            if attempt < 2:
                time.sleep(min(2 ** attempt, 8))
        else:
            raise DevToError(f"Dev.to API failed after retries: {last_error}")

        url = (data or {}).get("url")
        if not url:
            raise DevToError("Dev.to accepted the request but returned no article URL.")
        logger.info("Published article to Dev.to: {}", url)
        return {"url": url}
