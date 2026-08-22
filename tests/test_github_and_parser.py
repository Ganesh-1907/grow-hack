"""Tests for GitHub URL validation and parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from models.repository import RepositoryContext, RepositoryMetadata
from services.github_service import (
    InvalidRepositoryUrlError,
    ParsedRepositoryUrl,
    validate_repository_url,
)
from services.parser import RepositoryParser


def test_valid_repository_url():
    parsed = validate_repository_url("https://github.com/langchain-ai/langgraph/")
    assert parsed.owner == "langchain-ai"
    assert parsed.repo == "langgraph"
    assert parsed.url == "https://github.com/langchain-ai/langgraph"


def test_repository_url_without_github_is_invalid():
    with pytest.raises(InvalidRepositoryUrlError):
        validate_repository_url("https://gitlab.com/owner/repo")


def test_malformed_repository_url_is_invalid():
    with pytest.raises(InvalidRepositoryUrlError):
        validate_repository_url("https://github.com/onlyowner")


def test_parser_collects_readme_and_dependencies(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Demo", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("flask>=3.0\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text("ignored", encoding="utf-8")

    context = RepositoryContext(
        url="https://github.com/acme/demo",
        owner="acme",
        repo="demo",
        metadata=RepositoryMetadata(name="demo", full_name="acme/demo", html_url="https://github.com/acme/demo"),
        clone_path=str(tmp_path),
    )

    parser = RepositoryParser()
    parsed = parser.parse(context)

    assert parsed.readme == "# Demo"
    assert any(dep.name == "flask" for dep in parsed.dependencies)
    assert "app.py" in parsed.file_paths()
    assert all("node_modules" not in path for path in parsed.file_paths())


def test_parser_ignores_large_binary_files(tmp_path: Path):
    (tmp_path / "large.bin").write_bytes(b"\x00" * 1024)
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")

    context = RepositoryContext(
        url="https://github.com/acme/demo",
        owner="acme",
        repo="demo",
        metadata=RepositoryMetadata(name="demo", full_name="acme/demo", html_url="https://github.com/acme/demo"),
        clone_path=str(tmp_path),
    )

    parsed = RepositoryParser().parse(context)
    assert "large.bin" not in parsed.file_paths()
    assert "app.py" in parsed.file_paths()
