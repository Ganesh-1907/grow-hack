"""Prompt for reviewing and improving generated documentation."""

from __future__ import annotations

REVIEW_SYSTEM_PROMPT = """You are a meticulous technical documentation reviewer.
Improve grammar, formatting, consistency, and technical accuracy without changing the section structure.
Return only the revised Markdown document.
"""


def build_review_prompt(documentation: str) -> str:
    """Build the review prompt for a Markdown document.

    Args:
        documentation: The generated Markdown to review.

    Returns:
        A complete prompt requesting a revised Markdown document.
    """
    return f"""Review and improve the following Markdown documentation.

Requirements:
- Fix grammar and spelling.
- Normalize Markdown formatting and code fences.
- Ensure section headings are consistent.
- Correct technically inaccurate statements when the provided content allows.
- Keep the same sections and order.
- Do not add speculative information.

Documentation:
{documentation}

Return only the improved Markdown document."""
