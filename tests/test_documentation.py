"""Tests for the markdown, mock knowledge, and app routes."""

from __future__ import annotations

from pathlib import Path

from config import Config
from models.repository import RepositoryContext, RepositoryKnowledge, RepositoryMetadata
from services.markdown_service import MarkdownService
from services.llm_service import build_mock_knowledge


def make_context(tmp_path: Path) -> RepositoryContext:
    (tmp_path / "README.md").write_text("# Demo", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")

    return RepositoryContext(
        url="https://github.com/acme/demo",
        owner="acme",
        repo="demo",
        metadata=RepositoryMetadata(
            name="demo",
            full_name="acme/demo",
            html_url="https://github.com/acme/demo",
            description="A demo repository.",
        ),
        clone_path=str(tmp_path),
    )


def test_build_mock_knowledge_uses_context(tmp_path: Path):
    context = make_context(tmp_path)
    from services.parser import RepositoryParser

    context = RepositoryParser().parse(context)
    knowledge = build_mock_knowledge(context)

    assert knowledge.name == "demo"
    assert knowledge.language == "Python"
    assert knowledge.entry_points == ["app.py"]


def test_markdown_service_generates_sections(tmp_path: Path):
    config = Config(
        markdown_dir=tmp_path / "markdown",
        pdf_dir=tmp_path / "pdf",
        repos_dir=tmp_path / "repos",
    )
    config.ensure_directories()

    context = make_context(tmp_path)
    from services.parser import RepositoryParser

    context = RepositoryParser().parse(context)
    knowledge = build_mock_knowledge(context)

    generated = MarkdownService(config).generate(context, knowledge)

    assert "# demo" in generated.documentation_markdown
    assert "## Project Overview" in generated.documentation_markdown
    assert generated.markdown_path.endswith("_documentation.md")
    assert Path(generated.markdown_path).exists()


def test_index_route(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Full-Stack Content Creator" in response.data


def test_analyze_missing_url(client):
    response = client.post("/analyze", json={})
    assert response.status_code == 400
    assert b"Repository URL is required" in response.data
