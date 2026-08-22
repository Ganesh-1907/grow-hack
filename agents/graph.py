"""LangGraph workflow orchestrating the documentation pipeline."""

from __future__ import annotations

from typing import Any, TypedDict

from loguru import logger

from agents.analysis_agent import AnalysisAgent
from agents.documentation_agent import DocumentationAgent
from agents.github_agent import GitHubAgent
from agents.review_agent import ReviewAgent
from config import Config
from models.repository import GeneratedDocumentation, RepositoryContext, RepositoryKnowledge
from services.github_service import validate_repository_url
from services.markdown_service import write_readme_file
from services.pdf_service import PDFService
from services.parser import RepositoryParser


class WorkflowState(TypedDict, total=False):
    """Mutable state passed between LangGraph nodes."""

    url: str
    normalized_url: str
    context: RepositoryContext
    knowledge: RepositoryKnowledge
    generated: GeneratedDocumentation
    pdf_path: str
    error: str


class DocumentationGraph:
    """LangGraph-based pipeline from URL to generated documentation."""

    def __init__(self, config: Config) -> None:
        """Create the graph with injected service dependencies."""
        self.config = config
        self.github_agent = GitHubAgent(config)
        self.parser = RepositoryParser()
        self.analysis_agent = AnalysisAgent(config)
        self.documentation_agent = DocumentationAgent(config)
        self.review_agent = ReviewAgent(config)
        self.pdf_service = PDFService(config)
        self._graph = self._build_graph()

    def run(self, repo_url: str) -> dict[str, Any]:
        """Run the complete workflow for a repository URL.

        Args:
            repo_url: The public GitHub repository URL.

        Returns:
            Final workflow state containing generated artifacts and summary.
        """
        initial: WorkflowState = {"url": repo_url}
        return self._graph.invoke(initial)

    def _build_graph(self):
        """Construct the LangGraph StateGraph with linear pipeline nodes."""
        try:
            from langgraph.graph import END, StateGraph
        except ImportError as exc:  # pragma: no cover - exercised only when dep missing
            raise RuntimeError(
                "LangGraph is required. Install dependencies with `pip install -r requirements.txt`."
            ) from exc

        graph = StateGraph(WorkflowState)

        graph.add_node("validate_repository", self._validate_repository)
        graph.add_node("fetch_repository", self._fetch_repository)
        graph.add_node("parse_repository", self._parse_repository)
        graph.add_node("analyze_repository", self._analyze_repository)
        graph.add_node("generate_documentation", self._generate_documentation)
        graph.add_node("review_documentation", self._review_documentation)
        graph.add_node("generate_markdown", self._generate_markdown)
        graph.add_node("generate_pdf", self._generate_pdf)

        graph.set_entry_point("validate_repository")
        graph.add_edge("validate_repository", "fetch_repository")
        graph.add_edge("fetch_repository", "parse_repository")
        graph.add_edge("parse_repository", "analyze_repository")
        graph.add_edge("analyze_repository", "generate_documentation")
        graph.add_edge("generate_documentation", "review_documentation")
        graph.add_edge("review_documentation", "generate_markdown")
        graph.add_edge("generate_markdown", "generate_pdf")
        graph.add_edge("generate_pdf", END)

        return graph.compile()

    def _validate_repository(self, state: WorkflowState) -> WorkflowState:
        parsed = validate_repository_url(state["url"])
        logger.info("Validated repository {}", parsed.url)
        return {"normalized_url": parsed.url}

    def _fetch_repository(self, state: WorkflowState) -> WorkflowState:
        context = self.github_agent.github_service.fetch_repository_context(state["url"])
        logger.info("Fetched repository {}", context.metadata.full_name)
        return {"context": context}

    def _parse_repository(self, state: WorkflowState) -> WorkflowState:
        context = self.parser.parse(state["context"])
        logger.info("Parsed {} source files", context.text_files)
        return {"context": context}

    def _analyze_repository(self, state: WorkflowState) -> WorkflowState:
        knowledge = self.analysis_agent.run(state["context"])
        return {"knowledge": knowledge}

    def _generate_documentation(self, state: WorkflowState) -> WorkflowState:
        generated = self.documentation_agent.run(state["context"], state["knowledge"])
        return {"generated": generated}

    def _review_documentation(self, state: WorkflowState) -> WorkflowState:
        generated = self.review_agent.run(state["generated"])
        return {"generated": generated}

    def _generate_markdown(self, state: WorkflowState) -> WorkflowState:
        write_readme_file(self.config, state["generated"])
        return {}

    def _generate_pdf(self, state: WorkflowState) -> WorkflowState:
        try:
            pdf_path = self.pdf_service.generate(state["generated"])
            return {"pdf_path": pdf_path}
        except RuntimeError as exc:
            logger.warning("PDF generation unavailable: {}", exc)
            return {"pdf_path": ""}
