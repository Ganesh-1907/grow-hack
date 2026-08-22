"""Tests for Dev.to publishing and tag sanitization (no network required)."""

from __future__ import annotations

import json
import urllib.error

from agents.content_agent import sanitize_tags
from config import Config
from services.devto_service import DevToError, DevToService


class FakeResponse:
    def __init__(self, data: dict) -> None:
        self._data = json.dumps(data).encode("utf-8")

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None


class FakeURLHandler:
    def __init__(self, response: dict | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.last_request = None
        self.last_payload = None

    def __call__(self, request, timeout=None):
        self.last_request = request
        self.last_payload = json.loads(request.data)
        if self.error:
            raise self.error
        return FakeResponse(self.response or {})


def make_service(handler: FakeURLHandler, key: str = "test-devto-key") -> DevToService:
    config = Config(devto_api_key=key)
    service = DevToService(config)
    service._urlopen = handler
    return service


def test_publish_success_returns_url(monkeypatch) -> None:
    handler = FakeURLHandler(response={"url": "https://dev.to/user/my-post"})
    monkeypatch.setattr("urllib.request.urlopen", handler)
    service = make_service(handler)
    result = service.publish("My Title", "# Hello", tags=["ai", "python", "extra", "fourth", "fifth"])
    assert result["url"] == "https://dev.to/user/my-post"
    article = handler.last_payload["article"]
    assert article["title"] == "My Title"
    assert article["published"] is True
    assert article["tags"] == ["ai", "python", "extra", "fourth"]


def test_publish_error_on_http_failure(monkeypatch) -> None:
    error = urllib.error.HTTPError("https://dev.to/api/articles", 401, "Unauthorized", {}, None)
    handler = FakeURLHandler(error=error)
    monkeypatch.setattr("urllib.request.urlopen", handler)
    service = make_service(handler)
    try:
        service.publish("T", "body")
    except DevToError as exc:
        assert "401" in str(exc)
    else:
        raise AssertionError("expected DevToError")


def test_publish_raises_when_key_missing() -> None:
    config = Config(devto_api_key="")
    service = DevToService(config)
    assert service.is_configured() is False
    try:
        service.publish("T", "body")
    except DevToError as exc:
        assert "not configured" in str(exc)
    else:
        raise AssertionError("expected DevToError")


def test_sanitize_tags() -> None:
    assert sanitize_tags(["AI", "Python!!", "dev-to", "tag with spaces", "x" * 10, "dup", "dup"]) == [
        "ai",
        "python",
        "devto",
        "tagwithspaces",
    ]
    assert sanitize_tags("not-a-list") == []
    assert sanitize_tags([]) == []
