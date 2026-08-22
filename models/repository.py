"""Domain models for the GitHub documentation pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class RepositoryMetadata(BaseModel):
    """Metadata returned by the GitHub REST API."""

    name: str
    full_name: str
    description: str = ""
    html_url: HttpUrl
    default_branch: str = "main"
    language: str | None = None
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    topics: list[str] = Field(default_factory=list)
    license: str | None = None
    owner_display_name: str = ""
    created_at: str | None = None
    updated_at: str | None = None


class SourceFile(BaseModel):
    """A text source file identified in the repository."""

    path: str
    extension: str = ""
    language: str | None = None
    size_bytes: int = 0
    content: str = ""
    importance: float = 0.0


class DirectoryNode(BaseModel):
    """Node in the repository directory tree."""

    name: str
    path: str
    type: str = "file"
    children: list[DirectoryNode] = Field(default_factory=list)


class DependencyInfo(BaseModel):
    """Declared dependency with optional version/specifier."""

    name: str
    version: str = ""
    section: str = "dependencies"


class RepositoryContext(BaseModel):
    """Everything collected from GitHub and the local repository clone."""

    url: HttpUrl
    owner: str
    repo: str
    metadata: RepositoryMetadata
    clone_path: str | None = None
    directory_tree: DirectoryNode | None = None
    readme: str = ""
    readme_path: str | None = None
    files: list[SourceFile] = Field(default_factory=list)
    config_files: dict[str, str] = Field(default_factory=dict)
    dependencies: list[DependencyInfo] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    total_files: int = 0
    text_files: int = 0

    def file_paths(self) -> list[str]:
        """Return the paths of all collected source files."""
        return [file.path for file in self.files]


class RepositoryKnowledge(BaseModel):
    """AI-enriched understanding of a repository.

    This object is intentionally provider-agnostic so future content modules
    (blog, LinkedIn, X thread, tutorial) can consume it without re-analyzing
    the repository.
    """

    name: str
    full_name: str
    description: str = ""
    project_type: str = "unknown"
    language: str | None = None
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    package_manager: str | None = None
    dependencies: list[DependencyInfo] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    architecture: str = ""
    architecture_patterns: list[str] = Field(default_factory=list)
    key_modules: list[dict[str, Any]] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    how_it_works: str = ""
    configuration: list[dict[str, str]] = Field(default_factory=list)
    api_overview: str = ""
    best_practices: list[str] = Field(default_factory=list)
    future_improvements: list[str] = Field(default_factory=list)
    faq: list[dict[str, str]] = Field(default_factory=list)


class GeneratedDocumentation(BaseModel):
    """Final reviewed Markdown and associated file artifacts."""

    repository: str
    documentation_markdown: str = ""
    readme_markdown: str = ""
    markdown_path: str = ""
    pdf_path: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)
