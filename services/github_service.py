"""GitHub integration: URL validation, metadata, and repository cloning."""

from __future__ import annotations

import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from github import Auth, Github, GithubException, Repository
from git import Repo
from loguru import logger

from config import Config
from models.repository import RepositoryContext, RepositoryMetadata

GITHUB_URL_PATTERN = re.compile(
    r"^https?://(?:www\.)?github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)


class GitHubError(Exception):
    """Base error for GitHub integration failures."""


class InvalidRepositoryUrlError(GitHubError):
    """Raised when the supplied repository URL is malformed."""


class RepositoryFetchError(GitHubError):
    """Raised when repository metadata or clone cannot be retrieved."""


@dataclass(slots=True)
class ParsedRepositoryUrl:
    """Owner and repository name extracted from a valid GitHub URL."""

    owner: str
    repo: str
    url: str


def validate_repository_url(url: str) -> ParsedRepositoryUrl:
    """Validate and normalize a public GitHub repository URL.

    Args:
        url: User-provided GitHub URL.

    Returns:
        Parsed owner/repository information.

    Raises:
        InvalidRepositoryUrlError: If the URL is not a valid repository URL.
    """
    if not url or not isinstance(url, str):
        raise InvalidRepositoryUrlError("Repository URL is required.")

    cleaned = url.strip().rstrip("/")
    parsed = urlparse(cleaned)

    if parsed.scheme not in {"http", "https"}:
        raise InvalidRepositoryUrlError("Repository URL must use http or https.")

    match = GITHUB_URL_PATTERN.match(cleaned)
    if not match:
        raise InvalidRepositoryUrlError(
            "Enter a valid GitHub repository URL like https://github.com/owner/repository."
        )

    return ParsedRepositoryUrl(
        owner=match.group("owner"),
        repo=match.group("repo"),
        url=cleaned,
    )


class GitHubService:
    """Fetch GitHub metadata and clone public repositories."""

    def __init__(self, config: Config) -> None:
        """Create the service with injected configuration."""
        self.config = config
        self._github = Github(auth=Auth.Token(config.github_token)) if config.github_token else Github()

    def fetch_repository_context(self, url: str) -> RepositoryContext:
        """Validate a URL, fetch metadata, and clone the repository.

        Args:
            url: The public GitHub repository URL.

        Returns:
            A populated RepositoryContext containing metadata and clone path.
        """
        parsed = validate_repository_url(url)
        metadata = self._fetch_metadata(parsed)
        clone_path = self._clone_repository(parsed)

        return RepositoryContext(
            url=parsed.url,
            owner=parsed.owner,
            repo=parsed.repo,
            metadata=metadata,
            clone_path=str(clone_path),
        )

    def _fetch_metadata(self, parsed: ParsedRepositoryUrl) -> RepositoryMetadata:
        """Fetch repository metadata with retry support."""
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                repository: Repository = self._github.get_repo(f"{parsed.owner}/{parsed.repo}")
                license_name = None
                try:
                    license_info = repository.get_license()
                    license_name = license_info.license.name if license_info.license else None
                except GithubException:
                    license_name = None

                return RepositoryMetadata(
                    name=repository.name,
                    full_name=repository.full_name,
                    description=repository.description or "",
                    html_url=repository.html_url,
                    default_branch=repository.default_branch,
                    language=repository.language,
                    stars=repository.stargazers_count,
                    forks=repository.forks_count,
                    open_issues=repository.open_issues_count,
                    topics=list(repository.get_topics()),
                    license=license_name,
                    owner_display_name=(repository.owner.name or repository.owner.login)
                    if getattr(repository, "owner", None)
                    else parsed.owner,
                    created_at=repository.created_at.isoformat() if repository.created_at else None,
                    updated_at=repository.updated_at.isoformat() if repository.updated_at else None,
                )
            except GithubException as exc:
                last_error = exc
                logger.warning("GitHub metadata fetch failed on attempt {}", attempt + 1)
                time.sleep(2**attempt)

        raise RepositoryFetchError(f"Failed to fetch GitHub metadata: {last_error}")

    def _clone_repository(self, parsed: ParsedRepositoryUrl) -> Path:
        """Clone the repository to a sandboxed local directory.

        Existing clones are reused when possible to avoid repeated network
        usage, but a shallow clone is used initially for speed.
        """
        destination = self.config.repos_dir / f"{parsed.owner}_{parsed.repo}"
        clone_url = f"https://github.com/{parsed.owner}/{parsed.repo}.git"

        if destination.exists() and (destination / ".git").exists():
            logger.info("Reusing existing clone at {}", destination)
            return destination

        if destination.exists():
            shutil.rmtree(destination)

        try:
            logger.info("Cloning {} to {}", clone_url, destination)
            clone_env = os.environ.copy()
            timeout = self.config.clone_timeout_seconds
            # Git has no direct clone timeout; these options terminate a clone
            # that stalls on the network for the configured duration.
            clone_env["GIT_HTTP_LOW_SPEED_LIMIT"] = "1000"
            clone_env["GIT_HTTP_LOW_SPEED_TIME"] = str(timeout)
            Repo.clone_from(
                clone_url,
                destination,
                depth=1,
                single_branch=True,
                env=clone_env,
            )
        except Exception as exc:
            shutil.rmtree(destination, ignore_errors=True)
            raise RepositoryFetchError(f"Failed to clone repository: {exc}") from exc

        return destination
