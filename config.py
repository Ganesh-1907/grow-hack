"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent


def _env_bool(name: str, default: bool = False) -> bool:
    """Return a boolean value for an environment variable."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    """Return an integer value for an environment variable."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(slots=True)
class Config:
    """Typed application configuration.

    All secrets are read from the environment at import time and never
    hardcoded. Consumers receive this object through dependency injection.
    """

    flask_env: str = field(default_factory=lambda: os.getenv("FLASK_ENV", "development"))
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "dev-secret"))
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _env_int("PORT", 5000))

    github_token: str | None = field(default_factory=lambda: os.getenv("GITHUB_TOKEN"))
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "deepseek"))
    llm_api_key: str | None = field(
        default_factory=lambda: os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    )
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "deepseek-chat"))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.deepseek.com"))
    llm_timeout_seconds: int = field(default_factory=lambda: _env_int("LLM_TIMEOUT_SECONDS", 120))

    devto_api_key: str | None = field(default_factory=lambda: os.getenv("DEVTO_API_KEY"))
    author_name: str = field(default_factory=lambda: os.getenv("AUTHOR_NAME", "Ganesh Bora"))

    max_repository_size_mb: int = field(default_factory=lambda: _env_int("MAX_REPOSITORY_SIZE_MB", 100))
    clone_timeout_seconds: int = field(default_factory=lambda: _env_int("CLONE_TIMEOUT_SECONDS", 120))
    enable_mock_llm: bool = field(default_factory=lambda: _env_bool("ENABLE_MOCK_LLM", True))

    generated_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "generated")
    markdown_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "generated" / "markdown")
    pdf_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "generated" / "pdf")
    content_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "generated" / "content")
    repos_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "repos")

    @property
    def llm_available(self) -> bool:
        """Return whether a real LLM client can be constructed."""
        return bool(self.llm_api_key)

    def ensure_directories(self) -> None:
        """Create runtime directories used for clones and generated output."""
        for directory in (self.generated_dir, self.markdown_dir, self.pdf_dir, self.content_dir, self.repos_dir):
            directory.mkdir(parents=True, exist_ok=True)


def get_config() -> Config:
    """Build the application configuration and prepare runtime directories."""
    config = Config()
    config.ensure_directories()
    return config
