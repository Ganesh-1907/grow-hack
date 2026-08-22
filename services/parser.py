"""Repository parsing and static analysis utilities."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from loguru import logger

from models.repository import (
    DependencyInfo,
    DirectoryNode,
    RepositoryContext,
    SourceFile,
)

IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
    "__pycache__",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".next",
    ".nuxt",
    "target",
    ".gradle",
    "coverage",
}

IGNORED_FILES = {
    ".DS_Store",
    "Thumbs.db",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "go.sum",
    "Gemfile.lock",
    "composer.lock",
}

TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".java",
    ".kt",
    ".swift",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cs",
    ".scala",
    ".md",
    ".rst",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".sh",
    ".html",
    ".css",
    ".scss",
    ".sql",
    ".graphql",
    ".xml",
}

PACKAGE_FILES = {
    "package.json": "npm",
    "requirements.txt": "pip",
    "pyproject.toml": "python",
    "setup.py": "python",
    "Pipfile": "pipenv",
    "go.mod": "go",
    "Cargo.toml": "cargo",
    "Gemfile": "bundler",
    "composer.json": "composer",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle",
    "pubspec.yaml": "pub",
}

CONFIG_FILES = {
    ".env.example",
    ".env.sample",
    "config.py",
    "config.json",
    "settings.py",
    "application.yml",
    "application.yaml",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Dockerfile",
    "Makefile",
}

ENTRY_POINT_HINTS = {
    "app.py": 1.0,
    "main.py": 1.0,
    "manage.py": 0.9,
    "index.js": 0.9,
    "server.js": 0.8,
    "src/index.js": 0.8,
    "src/index.ts": 0.8,
    "src/main.py": 0.9,
    "src/app.py": 0.9,
    "main.go": 0.9,
    "src/main.rs": 0.9,
    "lib/main.dart": 0.9,
}

MAX_FILE_SIZE_BYTES = 500_000


class RepositoryParser:
    """Parse a cloned repository into structured context."""

    def __init__(self, max_file_size_bytes: int = MAX_FILE_SIZE_BYTES) -> None:
        """Create the parser with an optional file size limit."""
        self.max_file_size_bytes = max_file_size_bytes

    def parse(self, context: RepositoryContext) -> RepositoryContext:
        """Enrich a RepositoryContext with tree, files, configs, and dependencies.

        Args:
            context: Context already populated with metadata and clone path.

        Returns:
            The same context with parsed information added.
        """
        if not context.clone_path:
            raise ValueError("RepositoryContext is missing a clone_path.")

        root = Path(context.clone_path)
        if not root.exists():
            raise FileNotFoundError(f"Clone path does not exist: {root}")

        context.directory_tree = self._build_tree(root, root)
        context.readme, context.readme_path = self._read_readme(root)
        context.files = self._collect_files(root)
        context.config_files = self._collect_config_files(root)
        context.dependencies = self._parse_dependencies(root)
        context.entry_points = self._detect_entry_points(root)
        context.total_files = sum(1 for _ in root.rglob("*") if _.is_file())
        context.text_files = len(context.files)
        return context

    def _build_tree(self, root: Path, directory: Path) -> DirectoryNode:
        """Build a lightweight directory tree ignoring generated content."""
        node = DirectoryNode(
            name=directory.name if directory != root else root.name,
            path=str(directory.relative_to(root)) if directory != root else ".",
            type="directory",
        )

        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return node

        for entry in entries:
            if entry.name in IGNORED_DIRECTORIES:
                continue
            if entry.is_dir():
                child = self._build_tree(root, entry)
                node.children.append(child)
            elif entry.is_file() and entry.name not in IGNORED_FILES:
                node.children.append(
                    DirectoryNode(
                        name=entry.name,
                        path=str(entry.relative_to(root)),
                        type="file",
                    )
                )
        return node

    def _read_readme(self, root: Path) -> tuple[str, str | None]:
        """Return README content and its relative path, if present."""
        for filename in ("README.md", "readme.md", "README.rst", "README.txt", "README"):
            path = root / filename
            if path.exists():
                try:
                    return path.read_text(encoding="utf-8", errors="replace"), filename
                except OSError as exc:
                    logger.warning("Could not read README {}: {}", path, exc)
                    return "", filename
        return "", None

    def _collect_files(self, root: Path) -> list[SourceFile]:
        """Collect readable text files relevant to analysis."""
        files: list[SourceFile] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if self._should_ignore(path, root):
                continue
            if path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > self.max_file_size_bytes:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            relative = str(path.relative_to(root))
            files.append(
                SourceFile(
                    path=relative,
                    extension=path.suffix.lower(),
                    language=self._language_for_suffix(path.suffix.lower()),
                    size_bytes=size,
                    content=content,
                )
            )
        return files

    def _collect_config_files(self, root: Path) -> dict[str, str]:
        """Collect declared configuration and package manifest files."""
        configs: dict[str, str] = {}
        candidates = CONFIG_FILES | set(PACKAGE_FILES.keys())

        for filename in candidates:
            path = root / filename
            if path.exists():
                try:
                    configs[filename] = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    logger.warning("Could not read config file {}", path)
        return configs

    def _parse_dependencies(self, root: Path) -> list[DependencyInfo]:
        """Parse dependencies from common package manifest files."""
        dependencies: list[DependencyInfo] = []

        package_json = root / "package.json"
        if package_json.exists():
            dependencies.extend(self._dependencies_from_package_json(package_json))

        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            dependencies.extend(self._dependencies_from_pyproject(pyproject))

        requirements = root / "requirements.txt"
        if requirements.exists():
            dependencies.extend(self._dependencies_from_requirements(requirements))

        go_mod = root / "go.mod"
        if go_mod.exists():
            dependencies.extend(self._dependencies_from_go_mod(go_mod))

        return dependencies

    def _detect_entry_points(self, root: Path) -> list[str]:
        """Detect likely application entry points by filename."""
        entry_points: list[str] = []
        for hint, _score in sorted(ENTRY_POINT_HINTS.items(), key=lambda x: -x[1]):
            if (root / hint).exists():
                entry_points.append(hint)
        return entry_points

    def _dependencies_from_package_json(self, path: Path) -> list[DependencyInfo]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        result: list[DependencyInfo] = []
        for section in ("dependencies", "devDependencies"):
            for name, version in data.get(section, {}).items():
                result.append(DependencyInfo(name=name, version=str(version), section=section))
        return result

    def _dependencies_from_pyproject(self, path: Path) -> list[DependencyInfo]:
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError):
            return []
        result: list[DependencyInfo] = []
        poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
        for name, version in poetry_deps.items():
            if name == "python":
                continue
            result.append(DependencyInfo(name=name, version=str(version), section="dependencies"))
        project_deps = data.get("project", {}).get("dependencies", [])
        for dep in project_deps:
            result.append(DependencyInfo(name=str(dep), version="", section="dependencies"))
        return result

    def _dependencies_from_requirements(self, path: Path) -> list[DependencyInfo]:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        result: list[DependencyInfo] = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("-"):
                continue
            name = stripped.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip()
            if name:
                result.append(DependencyInfo(name=name, version=stripped, section="dependencies"))
        return result

    def _dependencies_from_go_mod(self, path: Path) -> list[DependencyInfo]:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        result: list[DependencyInfo] = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("module "):
                continue
            if " " not in stripped:
                continue
            name, version = stripped.split(" ", 1)
            if name and not name.startswith("require") and not name.startswith(")"):
                result.append(DependencyInfo(name=name, version=version.strip(), section="dependencies"))
        return result

    def _should_ignore(self, path: Path, root: Path) -> bool:
        """Return whether a file is under an ignored directory or ignored by name."""
        relative = path.relative_to(root)
        for part in relative.parts[:-1]:
            if part in IGNORED_DIRECTORIES:
                return True
        return path.name in IGNORED_FILES

    def _language_for_suffix(self, suffix: str) -> str | None:
        return {
            ".py": "Python",
            ".js": "JavaScript",
            ".jsx": "JavaScript",
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".go": "Go",
            ".rs": "Rust",
            ".rb": "Ruby",
            ".php": "PHP",
            ".java": "Java",
            ".kt": "Kotlin",
            ".swift": "Swift",
            ".c": "C",
            ".h": "C",
            ".cpp": "C++",
            ".hpp": "C++",
            ".cs": "C#",
            ".scala": "Scala",
            ".html": "HTML",
            ".css": "CSS",
            ".scss": "SCSS",
        }.get(suffix)


def flatten_tree(node: DirectoryNode, prefix: str = "", is_last: bool = True) -> list[str]:
    """Return a human-readable tree representation of a DirectoryNode."""
    lines: list[str] = []
    connector = "└── " if is_last else "├── "
    lines.append(f"{prefix}{connector}{node.name}/" if node.type == "directory" else f"{prefix}{connector}{node.name}")

    if node.children:
        child_prefix = prefix + ("    " if is_last else "│   ")
        for index, child in enumerate(node.children):
            lines.extend(flatten_tree(child, child_prefix, index == len(node.children) - 1))
    return lines
