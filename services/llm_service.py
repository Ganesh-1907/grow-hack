"""LLM integration with OpenAI-compatible providers and a deterministic fallback."""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from typing import Any

from loguru import logger
from openai import OpenAI

from config import Config
from models.repository import RepositoryContext, RepositoryKnowledge

JSON_PROMPT_SUFFIX = "\n\nReturn only valid JSON without markdown fences."
DEFAULT_SYSTEM_PROMPT = "You are a senior software architect that returns concise, accurate JSON."


class LLMError(Exception):
    """Raised when the LLM service fails after retries."""


class LLMService:
    """Thin LLM wrapper with retry support and mock fallback for local development."""

    def __init__(self, config: Config) -> None:
        """Create the service, optionally backed by a real LLM client."""
        self.config = config
        self._client: OpenAI | None = None
        if config.llm_api_key:
            self._client = OpenAI(
                api_key=config.llm_api_key,
                base_url=config.llm_base_url,
                timeout=config.llm_timeout_seconds,
            )

    def complete(
        self,
        prompt: str,
        temperature: float = 0.2,
        system_prompt: str | None = None,
    ) -> str:
        """Return a text completion using the configured LLM or mock generator.

        Args:
            prompt: The complete prompt to send.
            temperature: Sampling temperature.
            system_prompt: Optional system instruction; defaults to the
                architect prompt used by the documentation pipeline.

        Returns:
            Model-generated text.

        Raises:
            LLMError: If the LLM call fails and no fallback is available.
        """
        if self._client is None:
            if self.config.enable_mock_llm:
                logger.info("Using mock LLM fallback")
                return "{}"
            raise LLMError("LLM API key is not configured and mock LLM is disabled.")

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self._client.chat.completions.create(
                    model=self.config.llm_model,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt or DEFAULT_SYSTEM_PROMPT,
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=temperature,
                    max_tokens=8000,
                )
                content = response.choices[0].message.content
                if content:
                    return self._clean_reasoning_output(content)
            except Exception as exc:  # noqa: BLE001 - retries across many provider errors
                last_error = exc
                logger.warning("LLM call failed on attempt {}: {}", attempt + 1, exc)
                if attempt < 2:
                    time.sleep(min(2 ** attempt, 8))

        raise LLMError(f"LLM call failed after retries: {last_error}")

    def complete_json(self, prompt: str) -> dict[str, Any]:
        """Return a parsed JSON object from the LLM.

        Falls back to an empty object when running in mock mode so the
        application remains usable without an API key.
        """
        if self._client is None and self.config.enable_mock_llm:
            return {}

        raw = self.complete(prompt + JSON_PROMPT_SUFFIX)
        cleaned = self._clean_reasoning_output(raw)
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return self._extract_json_object(cleaned)

    def _clean_reasoning_output(self, raw: str) -> str:
        """Remove reasoning-model wrapper tags and surrounding whitespace.

        Some Groq models emit `<｜end▁of▁thinking｜>`{"hello":"world"}` where `raw` is a string.
        Remove `...` blocks and use only the final answer text.
        """
        cleaned = raw.strip()
        cleaned = re.sub(r"<\s*think\s*>.*?<\s*/\s*think\s*>", "", cleaned, flags=re.DOTALL)
        return cleaned.strip()

    def _extract_json_object(self, text: str) -> dict[str, Any]:
        """Best-effort extraction of the first JSON object from model output."""
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}


def build_mock_knowledge(context: RepositoryContext) -> RepositoryKnowledge:
    """Build deterministic RepositoryKnowledge without calling an LLM.

    This enables the full pipeline to run locally while the developer has no
    API key configured, and doubles as the baseline for tests.
    """
    languages = [file.language for file in context.files if file.language]
    language_counts = Counter(languages)
    primary_language = language_counts.most_common(1)[0][0] if language_counts else None

    frameworks = _infer_frameworks(context)
    package_manager = _infer_package_manager(context)
    features = _infer_features(context)

    return RepositoryKnowledge(
        name=context.metadata.name,
        full_name=context.metadata.full_name,
        description=context.metadata.description or _fallback_description(context),
        project_type=_infer_project_type(context),
        language=primary_language or context.metadata.language,
        languages=[lang for lang, _ in language_counts.most_common()],
        frameworks=frameworks,
        package_manager=package_manager,
        dependencies=context.dependencies,
        entry_points=context.entry_points,
        architecture=_describe_architecture(context),
        architecture_patterns=_infer_patterns(context),
        key_modules=_infer_key_modules(context),
        features=features,
        how_it_works=_describe_how_it_works(context),
        configuration=_infer_configuration(context),
        api_overview=_infer_api_overview(context),
        best_practices=_default_best_practices(),
        future_improvements=_default_future_improvements(),
        faq=_default_faq(context),
    )


def _infer_frameworks(context: RepositoryContext) -> list[str]:
    """Infer common frameworks from dependency and file names."""
    frameworks: list[str] = []
    dep_names = {dep.name.lower() for dep in context.dependencies}
    paths = " ".join(context.file_paths()).lower()
    readme = context.readme.lower()

    hints = {
        "django": ("django",),
        "flask": ("flask",),
        "fastapi": ("fastapi",),
        "react": ("react", "react-dom"),
        "next.js": ("next",),
        "vue": ("vue",),
        "express": ("express",),
        "nestjs": ("@nestjs/core", "nestjs"),
        "spring": ("spring-boot", "spring"),
        "rails": ("rails",),
        "laravel": ("laravel",),
        "langgraph": ("langgraph",),
    }
    for framework, keywords in hints.items():
        if any(keyword in dep_names or keyword in paths or keyword in readme for keyword in keywords):
            frameworks.append(framework)
    return frameworks


def _infer_package_manager(context: RepositoryContext) -> str | None:
    for filename in context.config_files:
        if filename == "package.json":
            return "npm"
        if filename == "requirements.txt":
            return "pip"
        if filename == "pyproject.toml":
            return "pip/poetry"
        if filename == "go.mod":
            return "go modules"
        if filename == "Cargo.toml":
            return "cargo"
    return None


def _infer_project_type(context: RepositoryContext) -> str:
    paths = " ".join(context.file_paths()).lower()
    if any("test" in path for path in context.file_paths()) and any(".py" in path for path in context.file_paths()):
        return "python-application"
    if "package.json" in context.config_files and ".ts" in paths:
        return "typescript-application"
    if "package.json" in context.config_files:
        return "javascript-application"
    if context.metadata.language:
        return f"{context.metadata.language.lower()}-project"
    return "application"


def _infer_features(context: RepositoryContext) -> list[str]:
    features: list[str] = []
    if context.readme:
        features.append("README documentation")
    if context.entry_points:
        features.append(f"Entry point: {context.entry_points[0]}")
    if context.dependencies:
        features.append(f"{len(context.dependencies)} declared dependencies")
    if any(path.endswith(("app.py", "server.py", "main.py")) for path in context.file_paths()):
        features.append("Application entry point detected")
    if not features:
        features.append("Source code organized under a standard project layout")
    return features


def _fallback_description(context: RepositoryContext) -> str:
    return (
        f"{context.metadata.name} is a public GitHub repository. "
        "Its structure and source files are described in the generated documentation."
    )


def _describe_architecture(context: RepositoryContext) -> str:
    return (
        "The repository follows a standard application layout. Source files are organized "
        "by responsibility, with configuration files and entry points at or near the root."
    )


def _infer_patterns(context: RepositoryContext) -> list[str]:
    patterns: list[str] = []
    paths = " ".join(context.file_paths()).lower()
    if "/services/" in paths or "services/" in paths:
        patterns.append("Service layer")
    if "/models/" in paths or "models/" in paths:
        patterns.append("Data models")
    if "/agents/" in paths or "agents/" in paths:
        patterns.append("Agent orchestration")
    if "/tests/" in paths or "test_" in paths:
        patterns.append("Automated testing")
    if "config" in paths:
        patterns.append("Centralized configuration")
    return patterns or ["Modular organization"]


def _infer_key_modules(context: RepositoryContext) -> list[dict[str, Any]]:
    modules: list[dict[str, Any]] = []
    for path in context.file_paths():
        if any(marker in path for marker in ("app.py", "main.py", "index.js", "main.go", "server.js")):
            modules.append({"path": path, "role": "Application entry point"})
        if path.endswith(("config.py", "settings.py")):
            modules.append({"path": path, "role": "Configuration"})
        if "/services/" in path and path.endswith(".py"):
            modules.append({"path": path, "role": "Service"})
        if "/agents/" in path and path.endswith(".py"):
            modules.append({"path": path, "role": "Agent"})
    return modules[:10]


def _describe_how_it_works(context: RepositoryContext) -> str:
    if context.entry_points:
        return (
            f"The application starts from `{context.entry_points[0]}` and delegates work "
            "to the supporting modules identified in the source tree."
        )
    return "The application initializes from its primary source modules and configuration files."


def _infer_configuration(context: RepositoryContext) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for name in sorted(context.config_files):
        result.append({"file": name, "purpose": f"{name} contains project configuration."})
    return result


def _infer_api_overview(context: RepositoryContext) -> str:
    for path in context.file_paths():
        if path.endswith(("app.py", "server.py", "main.py")) and ".py" in path:
            return (
                "The Python application exposes routes or handlers through its entry point. "
                "Refer to the source for endpoint-specific behavior."
            )
    return ""


def _default_best_practices() -> list[str]:
    return [
        "Keep configuration in environment variables rather than hardcoding secrets.",
        "Separate business logic from transport and presentation layers.",
        "Write automated tests for critical paths.",
        "Use dependency injection to keep modules testable and reusable.",
    ]


def _default_future_improvements() -> list[str]:
    return [
        "Expand test coverage across core modules.",
        "Add CI/CD pipelines for automated validation.",
        "Introduce structured API contracts where applicable.",
        "Publish reusable components to a package registry.",
    ]


def _default_faq(context: RepositoryContext) -> list[dict[str, str]]:
    return [
        {
            "question": "How do I run this project?",
            "answer": "Follow the installation steps and execute the detected entry point.",
        },
        {
            "question": "How is the project structured?",
            "answer": "The generated folder structure describes the top-level and source directories.",
        },
        {
            "question": "What dependencies does it use?",
            "answer": "Declared dependencies are listed in the Dependencies section of the documentation.",
        },
    ]
