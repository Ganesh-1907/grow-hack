"""GitHub Fetch Agent: validate, fetch metadata, clone, and parse."""

from __future__ import annotations

from config import Config
from models.repository import RepositoryContext
from services.github_service import GitHubService
from services.parser import RepositoryParser


class GitHubAgent:
    """Orchestrate repository acquisition and local parsing."""

    def __init__(self, config: Config) -> None:
        """Create the agent with its GitHub and parser dependencies."""
        self.config = config
        self.github_service = GitHubService(config)
        self.parser = RepositoryParser()

    def run(self, repo_url: str) -> RepositoryContext:
        """Fetch and parse a repository into a complete RepositoryContext.

        Args:
            repo_url: The public GitHub repository URL.

        Returns:
            A RepositoryContext enriched with metadata, tree, files, and config.
        """
        context = self.github_service.fetch_repository_context(repo_url)
        context = self.parser.parse(context)
        return context
