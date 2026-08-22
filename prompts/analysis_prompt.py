"""Prompt for repository analysis and knowledge extraction."""

from __future__ import annotations

from dataclasses import dataclass

from models.repository import RepositoryContext

ANALYSIS_SYSTEM_PROMPT = """You are a senior software architect performing repository analysis.
Return a single JSON object with the exact keys requested. Use only facts visible in the provided repository context.
Be precise, concise, and technically accurate. Do not invent files or dependencies.
"""

MAX_PROMPT_TOKENS = 7000


@dataclass(frozen=True, slots=True)
class PromptLimits:
    """Content limits for a single analysis prompt."""

    file_summary_items: int
    dependency_items: int
    readme_chars: int
    source_excerpts: int
    source_excerpt_chars: int


PROMPT_TIERS: tuple[PromptLimits, ...] = (
    PromptLimits(file_summary_items=300, dependency_items=200, readme_chars=4000, source_excerpts=12, source_excerpt_chars=2500),
    PromptLimits(file_summary_items=150, dependency_items=100, readme_chars=2500, source_excerpts=6, source_excerpt_chars=1800),
    PromptLimits(file_summary_items=80, dependency_items=60, readme_chars=1500, source_excerpts=4, source_excerpt_chars=1200),
    PromptLimits(file_summary_items=50, dependency_items=40, readme_chars=800, source_excerpts=2, source_excerpt_chars=800),
)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def build_analysis_prompt(context: RepositoryContext) -> str:
    """Build the analysis prompt from parsed repository context.

    The prompt includes README text, a compact file inventory, and source
    excerpts for the most relevant files. This prevents the model from
    relying only on the README and lets it ground architecture, module,
    configuration, and API claims in actual code.

    Content is sized in tiers so the total prompt stays within free-tier
    LLM token limits (8k TPM); the first tier whose estimate fits is used.

    Args:
        context: Parsed repository context including files and metadata.

    Returns:
        A complete prompt requesting structured JSON analysis.
    """
    for limits in PROMPT_TIERS:
        prompt = _render_prompt(context, limits)
        if _estimate_tokens(prompt) <= MAX_PROMPT_TOKENS:
            return prompt
    return _render_prompt(context, PROMPT_TIERS[-1])


def _render_prompt(context: RepositoryContext, limits: PromptLimits) -> str:
    readme_preview = context.readme[: limits.readme_chars] if context.readme else "No README found."
    file_summary = "\n".join(
        f"- {file.path} ({file.language or 'unknown'}, {file.size_bytes} bytes)"
        for file in context.files[: limits.file_summary_items]
    )
    dependency_summary = ", ".join(
        f"{dep.name}" + (f"@{dep.version}" if dep.version else "")
        for dep in context.dependencies[: limits.dependency_items]
    ) or "None"

    source_excerpts = _build_source_excerpts(context, limits)

    return f"""Analyze the following GitHub repository using the README, file inventory, and source excerpts below.

Repository: {context.metadata.full_name}
Description: {context.metadata.description or "No description"}
Primary language from GitHub: {context.metadata.language or "Unknown"}
Topics: {", ".join(context.metadata.topics) if context.metadata.topics else "None"}
Entry point candidates: {", ".join(context.entry_points) if context.entry_points else "None"}
Declared dependencies: {dependency_summary}

README preview:
{readme_preview}

Collected source files:
{file_summary}

Important source file excerpts:
{source_excerpts}

Return a JSON object with these keys:
{{
  "description": "string",
  "project_type": "string",
  "language": "string or null",
  "languages": ["string"],
  "frameworks": ["string"],
  "package_manager": "string or null",
  "architecture": "string explaining the high-level architecture",
  "architecture_patterns": ["string"],
  "key_modules": [{{"path": "string", "role": "string"}}],
  "features": ["string"],
  "how_it_works": "string",
  "configuration": [{{"file": "string", "purpose": "string"}}],
  "api_overview": "string or empty string",
  "best_practices": ["string"],
  "future_improvements": ["string"],
  "faq": [{{"question": "string", "answer": "string"}}]
}}"""


def _build_source_excerpts(context: RepositoryContext, limits: PromptLimits) -> str:
    """Return a bounded excerpt block for the most analysis-relevant files."""
    relevant = [
        file
        for file in context.files
        if _is_relevant_source_file(file.path)
    ][: limits.source_excerpts]

    blocks: list[str] = []
    for file in relevant:
        content = file.content.strip()
        if not content:
            continue
        preview = content[: limits.source_excerpt_chars]
        truncated = " [truncated]" if len(content) > limits.source_excerpt_chars else ""
        blocks.append(
            f"--- FILE: {file.path} ({file.language or 'unknown'}) ---\n{preview}{truncated}"
        )

    if not blocks:
        return "No relevant source excerpts were available."

    return "\n\n".join(blocks)


def _is_relevant_source_file(path: str) -> bool:
    """Return whether a source file should be excerpted for the LLM.

    Excludes documentation, generated files, tests, lockfiles, and other
    low-signal paths so the excerpt budget is spent on application code.
    """
    lowered = path.lower()
    excluded_markers = (
        "readme",
        "changelog",
        "license",
        ".test.",
        ".spec.",
        "/tests/",
        "/test/",
        "/__tests__/",
        "lock",
        "/dist/",
        "/build/",
        "/node_modules/",
        "/docs/",
        "migrations",
    )
    return not any(marker in lowered for marker in excluded_markers)
