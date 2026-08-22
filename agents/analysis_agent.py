"""Repository Analysis Agent: convert context into structured knowledge."""

from __future__ import annotations

from loguru import logger

from config import Config
from models.repository import RepositoryContext, RepositoryKnowledge
from prompts.analysis_prompt import build_analysis_prompt
from services.llm_service import LLMService, build_mock_knowledge


class AnalysisAgent:
    """Analyze a repository using an LLM with a deterministic fallback."""

    def __init__(self, config: Config, llm_service: LLMService | None = None) -> None:
        """Create the analysis agent with injected LLM service."""
        self.config = config
        self.llm_service = llm_service or LLMService(config)

    def run(self, context: RepositoryContext) -> RepositoryKnowledge:
        """Produce RepositoryKnowledge from parsed repository context.

        Args:
            context: Parsed repository context.

        Returns:
            RepositoryKnowledge populated by the LLM or deterministic fallback.
        """
        prompt = build_analysis_prompt(context)

        if self.llm_service._client is None and self.config.enable_mock_llm:
            logger.info("AnalysisAgent using deterministic mock knowledge")
            return build_mock_knowledge(context)

        try:
            data = self.llm_service.complete_json(prompt)
            if not data:
                logger.info("Empty LLM analysis; falling back to deterministic knowledge")
                return build_mock_knowledge(context)
            return self._merge_knowledge(context, data)
        except Exception as exc:  # noqa: BLE001 - preserve pipeline robustness
            logger.warning("LLM analysis failed, using fallback: {}", exc)
            return build_mock_knowledge(context)

    def _merge_knowledge(self, context: RepositoryContext, data: dict) -> RepositoryKnowledge:
        """Merge LLM output with deterministic facts from parsing.

        Parsed dependencies and entry points are authoritative and are merged
        back in to avoid the LLM dropping or inventing them.
        """
        knowledge = RepositoryKnowledge(
            name=context.metadata.name,
            full_name=context.metadata.full_name,
            description=data.get("description") or context.metadata.description,
            project_type=data.get("project_type") or "unknown",
            language=data.get("language") or context.metadata.language,
            languages=data.get("languages") or [],
            frameworks=data.get("frameworks") or [],
            package_manager=data.get("package_manager"),
            dependencies=context.dependencies,
            entry_points=context.entry_points,
            architecture=data.get("architecture") or "",
            architecture_patterns=data.get("architecture_patterns") or [],
            key_modules=data.get("key_modules") or [],
            features=data.get("features") or [],
            how_it_works=data.get("how_it_works") or "",
            configuration=data.get("configuration") or [],
            api_overview=data.get("api_overview") or "",
            best_practices=data.get("best_practices") or [],
            future_improvements=data.get("future_improvements") or [],
            faq=data.get("faq") or [],
        )
        return knowledge
