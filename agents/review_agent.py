"""Review Agent: improve generated documentation quality."""

from __future__ import annotations

from loguru import logger

from config import Config
from models.repository import GeneratedDocumentation
from prompts.review_prompt import build_review_prompt
from services.llm_service import LLMService

MAX_DOC_CHARS = 28000


class ReviewAgent:
    """Review and optionally revise generated Markdown using an LLM."""

    def __init__(self, config: Config, llm_service: LLMService | None = None) -> None:
        """Create the review agent with injected LLM service."""
        self.config = config
        self.llm_service = llm_service or LLMService(config)

    def run(self, generated: GeneratedDocumentation) -> GeneratedDocumentation:
        """Review the generated Markdown and update it when a reviewer is available.

        Args:
            generated: Generated documentation to review.

        Returns:
            The same object with reviewed markdown when applicable.
        """
        if self.llm_service._client is None:
            logger.info("Skipping LLM review; no API key configured")
            return generated

        if len(generated.documentation_markdown) > MAX_DOC_CHARS:
            logger.info(
                "Skipping LLM review; documentation exceeds {} chars, keeping original markdown",
                MAX_DOC_CHARS,
            )
            return generated

        prompt = build_review_prompt(generated.documentation_markdown)
        try:
            reviewed = self.llm_service.complete(prompt)
            if reviewed and reviewed.strip():
                generated.documentation_markdown = reviewed.strip()
        except Exception as exc:  # noqa: BLE001 - review is best-effort
            logger.warning("ReviewAgent failed, keeping original markdown: {}", exc)

        return generated
