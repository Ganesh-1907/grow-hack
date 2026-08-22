"""Prompt for documentation generation."""

from __future__ import annotations

from models.repository import RepositoryContext, RepositoryKnowledge

DOCS_SYSTEM_PROMPT = """You are a technical writer producing clear, professional documentation.
Use the provided knowledge object and follow the requested Markdown section order exactly.
"""


def build_documentation_prompt(context: RepositoryContext, knowledge: RepositoryKnowledge) -> str:
    """Build the documentation prompt from repository knowledge.

    Args:
        context: Parsed repository context for folder structure and metadata.
        knowledge: Structured repository knowledge produced by analysis.

    Returns:
        A complete prompt requesting full Markdown documentation.
    """
    knowledge_json = knowledge.model_dump_json(indent=2)

    return f"""Generate comprehensive developer documentation in Markdown.

Repository metadata:
Name: {context.metadata.full_name}
Language: {context.metadata.language or "Unknown"}
Stars: {context.metadata.stars}
Forks: {context.metadata.forks}
Description: {context.metadata.description or "None"}

Repository knowledge JSON:
{knowledge_json}

Include these sections in order:
1. # {knowledge.name}
2. ## Project Overview
3. ## Project Purpose
4. ## Features
5. ## Architecture Overview
6. ## Architecture Patterns
7. ## Folder Structure (use a fenced tree; the actual tree is supplied below)
8. ## Installation
9. ## Quick Start
10. ## Configuration
11. ## Dependencies
12. ## How It Works
13. ## Important Modules
14. ## Example Usage
15. ## API Overview
16. ## Best Practices
17. ## FAQ
18. ## Future Improvements

Return only the Markdown document."""
