"""Documentation Agent: render RepositoryKnowledge into Markdown."""

from __future__ import annotations

from config import Config
from models.repository import GeneratedDocumentation, RepositoryContext, RepositoryKnowledge
from services.markdown_service import MarkdownService


class DocumentationAgent:
    """Generate documentation Markdown from repository knowledge."""

    def __init__(self, config: Config, markdown_service: MarkdownService | None = None) -> None:
        """Create the documentation agent with injected Markdown service."""
        self.config = config
        self.markdown_service = markdown_service or MarkdownService(config)

    def run(
        self,
        context: RepositoryContext,
        knowledge: RepositoryKnowledge,
    ) -> GeneratedDocumentation:
        """Generate documentation from context and knowledge.

        Args:
            context: Parsed repository context.
            knowledge: Repository knowledge produced by analysis.

        Returns:
            GeneratedDocumentation containing full Markdown and a persisted file path.
        """
        return self.markdown_service.generate(context, knowledge)
