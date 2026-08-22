"""Content Production Agent: topic or repo in, publish-ready content JSON out.

Implements the autonomous content-agent contract: input classification,
research pass, draft + self-review pass, defensive JSON parsing, and a
contract-shaped fallback so the pipeline never returns an error or an empty
response.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from loguru import logger

from agents.github_agent import GitHubAgent
from config import Config
from models.repository import RepositoryContext
from prompts.analysis_prompt import PROMPT_TIERS, _build_source_excerpts, _estimate_tokens
from prompts.content_prompt import CONTENT_SYSTEM_PROMPT, build_draft_message, build_research_message
from services.cover_service import find_repo_logo
from services.llm_service import LLMService

MAX_DIGEST_TOKENS = 5000

CONTRACT_KEYS = (
    "input_type",
    "interpreted_as",
    "title",
    "content_markdown",
    "image_prompts",
    "tags",
    "notes_for_judge",
)

_REPO_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org)/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
)
_REPO_FILE_MARKERS = (
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "go.mod",
    "cargo.toml",
    "dockerfile",
    "setup.py",
    "readme.md",
    ".tsx",
    "import react",
    "from flask",
    "def main(",
)


class ContentAgent:
    """Produce a publish-ready content contract from a topic or repo input."""

    def __init__(
        self,
        config: Config,
        llm_service: LLMService | None = None,
        github_agent: GitHubAgent | None = None,
    ) -> None:
        """Create the agent with injected services."""
        self.config = config
        self.llm_service = llm_service or LLMService(config)
        self.github_agent = github_agent or GitHubAgent(config)

    def run(self, input_text: str) -> dict[str, Any]:
        """Run the full content production flow for one input.

        Args:
            input_text: A topic (free text) or a GitHub repository URL.

        Returns:
            The OUTPUT CONTRACT dict with input_type, interpreted_as, title,
            content_markdown, image_prompts, and notes_for_judge.
        """
        raw = (input_text or "").strip()
        input_type = self.classify_input(raw)
        language = detect_language(raw)
        judge_notes: list[str] = []
        self._logo_path: str | None = None
        self._author_name: str | None = None

        resolved_input, sampled = self._resolve_repo(raw, input_type, judge_notes)

        research_notes = self._research_pass(resolved_input, language)

        if self.llm_service._client is None and self.config.enable_mock_llm:
            logger.info("ContentAgent using mock LLM fallback")
            fallback = self._fallback_contract(input_type, raw, research_notes, judge_notes)
            fallback["cover_author"] = self._author_name or self.config.author_name
            return fallback

        try:
            raw_output = self.llm_service.complete(
                build_draft_message(resolved_input, research_notes, language),
                temperature=0.5,
                system_prompt=CONTENT_SYSTEM_PROMPT,
            )
        except Exception as exc:  # noqa: BLE001 - never let the judge see a crash
            logger.warning("ContentAgent draft pass failed: {}", exc)
            return self._fallback_contract(input_type, raw, research_notes, judge_notes)

        contract = self._parse_contract(raw_output)
        self._finalize_contract(contract, input_type, raw, judge_notes)
        if self._logo_path:
            contract["cover_logo_path"] = self._logo_path
        contract["cover_author"] = self._author_name or self.config.author_name
        return contract

    def _resolve_repo(self, raw: str, input_type: str, judge_notes: list[str]) -> tuple[str, bool]:
        """Fetch and digest a repo input; returns (resolved input, sampled)."""
        if input_type != "repo":
            return raw, False
        try:
            context = self.github_agent.run(raw)
            digest, sampled = self._build_repo_digest(context)
            if sampled:
                judge_notes.append("Repository was sampled/truncated to fit token limits, not read in full.")
            if not (context.readme or "").strip():
                judge_notes.append("Repository has no README; purpose was inferred from source files.")
            self._logo_path = find_repo_logo(context)
            if self._logo_path:
                judge_notes.append("Found a repository logo; using it on the cover image.")
            self._author_name = context.metadata.owner_display_name or context.owner
            return digest, sampled
        except Exception as exc:  # noqa: BLE001 - honest fallback per the contract
            logger.warning("ContentAgent repo fetch failed: {}", exc)
            judge_notes.append(f"Repository could not be fetched ({exc}); the piece was written honestly from the raw URL.")
            return raw, False

    def _research_pass(self, resolved_input: str, language: str) -> str | None:
        """Best-effort research pass; the draft pass still works without it."""
        if self.llm_service._client is None:
            return None
        try:
            return self.llm_service.complete(
                build_research_message(resolved_input, language),
                temperature=0.3,
                system_prompt=CONTENT_SYSTEM_PROMPT,
            )
        except Exception as exc:  # noqa: BLE001 - research is optional
            logger.warning("ContentAgent research pass failed: {}", exc)
            return None

    def _build_repo_digest(self, context: RepositoryContext) -> tuple[str, bool]:
        """Render a token-bounded repo digest, tiered like the analysis prompt."""
        for index, limits in enumerate(PROMPT_TIERS):
            digest = self._render_digest(context, limits)
            if _estimate_tokens(digest) <= MAX_DIGEST_TOKENS:
                return digest, index != 0
        return self._render_digest(context, PROMPT_TIERS[-1]), True

    def _render_digest(self, context: RepositoryContext, limits: Any) -> str:
        readme = context.readme[: limits.readme_chars] or "No README found."
        file_summary = "\n".join(
            f"- {file.path} ({file.language or 'unknown'}, {file.size_bytes} bytes)"
            for file in context.files[: limits.file_summary_items]
        )
        dependency_summary = ", ".join(
            f"{dep.name}" + (f"@{dep.version}" if dep.version else "")
            for dep in context.dependencies[: limits.dependency_items]
        ) or "None"
        excerpts = _build_source_excerpts(context, limits)
        return f"""Repository: {context.metadata.full_name}
Description: {context.metadata.description or "No description"}
Primary language: {context.metadata.language or "Unknown"}
Entry point candidates: {", ".join(context.entry_points) or "None"}
Declared dependencies: {dependency_summary}

README:
{readme}

Collected source files:
{file_summary}

Important source file excerpts:
{excerpts}"""

    def _parse_contract(self, raw: str) -> dict[str, Any]:
        """Parse model output into the contract, tolerating fences and noise."""
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        data: Any = None
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            data = extract_json_object(cleaned)
        if not isinstance(data, dict) or not data:
            logger.warning("ContentAgent output was not a JSON object; wrapping raw text")
            return self._fallback_contract("unknown", cleaned, None, [])
        for key in CONTRACT_KEYS:
            data.setdefault(key, "" if key not in {"image_prompts", "tags"} else [])
        return data

    def _finalize_contract(self, contract: dict[str, Any], input_type: str, raw: str, judge_notes: list[str]) -> None:
        """Enforce classification and fold internal notes into notes_for_judge."""
        if contract.get("input_type") not in {"topic", "repo", "ambiguous"}:
            contract["input_type"] = input_type
        if input_type == "ambiguous" and not contract.get("interpreted_as"):
            contract["interpreted_as"] = f"Interpreted as: {raw[:120] or 'a publish-worthy topic'}"
        internal_notes = contract.get("notes_for_judge") or ""
        combined = "; ".join(note for note in [internal_notes, *judge_notes] if note)
        contract["notes_for_judge"] = combined
        if not contract.get("content_markdown"):
            contract["content_markdown"] = raw or "_No content was produced._"
        if not isinstance(contract.get("image_prompts"), list):
            contract["image_prompts"] = []
        contract["tags"] = sanitize_tags(contract.get("tags"))

    def _fallback_contract(
        self,
        input_type: str,
        raw: str,
        research_notes: str | None,
        judge_notes: list[str],
    ) -> dict[str, Any]:
        """Return a contract-shaped fallback so the run never errors out."""
        body = research_notes or raw or "No content could be generated."
        notes = "; ".join(note for note in ["Output was not valid JSON; raw text shown.", *judge_notes] if note)
        return {
            "input_type": input_type or "unknown",
            "interpreted_as": "",
            "title": "Generated Content",
            "content_markdown": body,
            "image_prompts": [],
            "tags": [],
            "notes_for_judge": notes,
        }

    def classify_input(self, text: str) -> str:
        """Classify input as repo, topic, or ambiguous."""
        value = (text or "").strip()
        if not value:
            return "ambiguous"
        if _REPO_URL_RE.search(value):
            return "repo"
        lowered = value.lower()
        if any(marker in lowered for marker in _REPO_FILE_MARKERS) and ("/" in value or "\n" in value):
            return "repo"
        if len(value.split()) == 1:
            return "ambiguous"
        return "topic"


def detect_language(text: str) -> str:
    """Return the dominant script language for the input (English by default)."""
    script_hints = (
        ("Hindi", "\u0900-\u097F"),
        ("Chinese", "\u4E00-\u9FFF"),
        ("Japanese", "\u3040-\u30FF"),
        ("Korean", "\uAC00-\uD7AF"),
        ("Russian", "\u0400-\u04FF"),
        ("Arabic", "\u0600-\u06FF"),
    )
    for language, span in script_hints:
        if re.search(f"[{span}]", text):
            return language
    return "English"


def extract_json_object(text: str) -> dict[str, Any]:
    """Best-effort extraction of the first JSON object from model output."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}


def sanitize_tags(tags: Any) -> list[str]:
    """Normalize tags to Dev.to rules: max 4, lowercase alphanumeric only."""
    if not isinstance(tags, list):
        return []
    cleaned: list[str] = []
    for tag in tags:
        if not isinstance(tag, str):
            continue
        normalized = re.sub(r"[^a-z0-9]", "", tag.strip().lower())
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
        if len(cleaned) == 4:
            break
    return cleaned
