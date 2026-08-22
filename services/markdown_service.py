"""Markdown generation and file persistence."""

from __future__ import annotations

import re
from pathlib import Path

from config import Config
from models.repository import GeneratedDocumentation, RepositoryContext, RepositoryKnowledge


class MarkdownService:
    """Render RepositoryKnowledge into professional Markdown documents."""

    def __init__(self, config: Config) -> None:
        """Create the service with injected configuration."""
        self.config = config

    def generate(
        self,
        context: RepositoryContext,
        knowledge: RepositoryKnowledge,
    ) -> GeneratedDocumentation:
        """Generate README and full documentation Markdown.

        Args:
            context: Parsed repository context with tree and metadata.
            knowledge: AI-derived repository knowledge.

        Returns:
            GeneratedDocumentation populated with markdown and a file path.
        """
        documentation = self._render_documentation(context, knowledge)
        readme = self._render_readme(context, knowledge)

        safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", knowledge.name) or "repository"
        markdown_path = self.config.markdown_dir / f"{safe_name}_documentation.md"
        markdown_path.write_text(documentation, encoding="utf-8")

        return GeneratedDocumentation(
            repository=knowledge.full_name or knowledge.name,
            documentation_markdown=documentation,
            readme_markdown=readme,
            markdown_path=str(markdown_path),
            summary=self._build_summary(context, knowledge),
        )

    def _render_documentation(
        self,
        context: RepositoryContext,
        knowledge: RepositoryKnowledge,
    ) -> str:
        tree = self._tree_string(context)
        architecture_section = knowledge.architecture

        sections: list[str] = [
            f"# {knowledge.name}\n\n> {knowledge.description}\n",
            "## Project Overview",
            knowledge.description,
            "## Project Purpose",
            self._purpose(knowledge),
            "## Features",
            self._bullet_list(knowledge.features),
            "## Architecture Overview",
            architecture_section,
            "## Architecture Patterns",
            self._bullet_list(knowledge.architecture_patterns),
            "## Folder Structure",
            f"```\n{tree}\n```",
            "## Installation",
            self._installation(knowledge),
            "## Quick Start",
            self._quick_start(context, knowledge),
            "## Configuration",
            self._configuration(knowledge),
            "## Dependencies",
            self._dependencies(knowledge),
            "## How It Works",
            knowledge.how_it_works,
            "## Important Modules",
            self._modules(knowledge),
            "## Example Usage",
            self._example_usage(context, knowledge),
            "## API Overview",
            knowledge.api_overview or "No public API surface was detected.",
            "## Best Practices",
            self._bullet_list(knowledge.best_practices),
            "## FAQ",
            self._faq(knowledge),
            "## Future Improvements",
            self._bullet_list(knowledge.future_improvements),
        ]
        return "\n\n".join(section for section in sections if section)

    def _render_readme(self, context: RepositoryContext, knowledge: RepositoryKnowledge) -> str:
        return "\n\n".join(
            [
                f"# {knowledge.name}",
                knowledge.description,
                "## Features",
                self._bullet_list(knowledge.features),
                "## Quick Start",
                self._quick_start(context, knowledge),
                "## Folder Structure",
                f"```\n{self._tree_string(context)}\n```",
            ]
        )

    def _build_summary(self, context: RepositoryContext, knowledge: RepositoryKnowledge) -> dict[str, str | int | list[str]]:
        return {
            "name": knowledge.name,
            "language": knowledge.language or context.metadata.language or "Unknown",
            "framework": ", ".join(knowledge.frameworks) or "Not detected",
            "package_manager": knowledge.package_manager or "Not detected",
            "project_type": knowledge.project_type,
            "stars": context.metadata.stars,
            "forks": context.metadata.forks,
            "files": context.text_files,
            "entry_points": context.entry_points,
            "description": knowledge.description,
        }

    def _tree_string(self, context: RepositoryContext) -> str:
        if context.directory_tree is None:
            return context.metadata.name
        from services.parser import flatten_tree

        node = context.directory_tree
        return "\n".join(flatten_tree(node))

    def _purpose(self, knowledge: RepositoryKnowledge) -> str:
        return (
            knowledge.description
            or f"{knowledge.name} is a {knowledge.project_type} project."
        )

    def _bullet_list(self, items: list[str] | list[dict[str, str]]) -> str:
        if not items:
            return "_Not specified._"
        lines: list[str] = []
        for item in items:
            if isinstance(item, dict):
                title = item.get("question") or item.get("role") or item.get("path", "")
                detail = item.get("answer") or item.get("purpose", "")
                lines.append(f"- **{title}**" + (f": {detail}" if detail else ""))
            else:
                lines.append(f"- {item}")
        return "\n".join(lines)

    def _installation(self, knowledge: RepositoryKnowledge) -> str:
        if knowledge.package_manager == "npm":
            return "```bash\nnpm install\n```"
        if knowledge.package_manager in {"pip", "pip/poetry"}:
            return "```bash\npip install -r requirements.txt\n```"
        if knowledge.package_manager == "go modules":
            return "```bash\ngo mod download\n```"
        if knowledge.package_manager == "cargo":
            return "```bash\ncargo build\n```"
        return "```bash\n# Install dependencies using the project's declared package manager\n```"

    def _quick_start(self, context: RepositoryContext, knowledge: RepositoryKnowledge) -> str:
        entry = knowledge.entry_points[0] if knowledge.entry_points else (context.entry_points[0] if context.entry_points else None)
        if entry and entry.endswith(".py"):
            return f"```bash\npython {entry}\n```"
        if entry and entry.endswith((".js", ".ts")):
            return f"```bash\nnode {entry}\n```"
        if entry and entry.endswith(".go"):
            return f"```bash\ngo run {entry}\n```"
        return "```bash\n# Run the project using the entry point shown in the Important Modules section\n```"

    def _configuration(self, knowledge: RepositoryKnowledge) -> str:
        if not knowledge.configuration:
            return "No dedicated configuration files were detected."
        lines: list[str] = []
        for item in knowledge.configuration:
            lines.append(f"- **{item.get('file', 'Configuration')}** - {item.get('purpose', '')}")
        return "\n".join(lines)

    def _dependencies(self, knowledge: RepositoryKnowledge) -> str:
        if not knowledge.dependencies:
            return "No dependencies were detected."
        return self._bullet_list(
            [
                {"question": dep.name, "answer": dep.version or "latest"}
                for dep in knowledge.dependencies
            ]
        )

    def _modules(self, knowledge: RepositoryKnowledge) -> str:
        if not knowledge.key_modules:
            return "No key modules were identified."
        return self._bullet_list(knowledge.key_modules)

    def _example_usage(self, context: RepositoryContext, knowledge: RepositoryKnowledge) -> str:
        if context.readme:
            return "The repository README contains project-specific usage details."
        return "Usage follows the Quick Start instructions and the behavior of the detected entry point."

    def _faq(self, knowledge: RepositoryKnowledge) -> str:
        if not knowledge.faq:
            return "No FAQ entries were generated."
        return self._bullet_list(knowledge.faq)


def write_readme_file(config: Config, generated: GeneratedDocumentation) -> str:
    """Persist the README variant and return its path."""
    safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", generated.repository) or "repository"
    path = config.markdown_dir / f"{safe_name}_README.md"
    path.write_text(generated.readme_markdown, encoding="utf-8")
    return str(path)
