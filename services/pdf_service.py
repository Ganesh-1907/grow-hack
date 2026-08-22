"""PDF generation from Markdown using WeasyPrint."""

from __future__ import annotations

import re

from loguru import logger

from config import Config
from models.repository import GeneratedDocumentation

PDF_STYLE = """
@page { margin: 2.5cm 2cm; }
body { font-family: 'DejaVu Sans', sans-serif; font-size: 11px; line-height: 1.5; color: #1f2937; }
h1 { font-size: 24px; margin-bottom: 4px; }
h2 { font-size: 18px; margin-top: 24px; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; }
h3 { font-size: 14px; margin-top: 16px; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 10px; background: #f3f4f6; padding: 2px 4px; }
pre { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 12px; overflow: hidden; }
pre code { background: none; padding: 0; }
blockquote { border-left: 4px solid #d1d5db; margin: 0; padding-left: 12px; color: #4b5563; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #e5e7eb; padding: 6px; text-align: left; }
"""


class PDFService:
    """Convert Markdown content into a styled PDF file."""

    def __init__(self, config: Config) -> None:
        """Create the service with injected configuration."""
        self.config = config

    def generate(self, generated: GeneratedDocumentation) -> str:
        """Generate a PDF from the documentation Markdown.

        Args:
            generated: Documentation with markdown content.

        Returns:
            Absolute path to the generated PDF.

        Raises:
            RuntimeError: If WeasyPrint is not installed or rendering fails.
        """
        try:
            import markdown as markdown_lib
            from weasyprint import HTML
        except ImportError as exc:
            raise RuntimeError(
                "PDF dependencies are not installed. Install requirements.txt to enable PDF export."
            ) from exc

        html_body = markdown_lib.markdown(
            generated.documentation_markdown,
            extensions=["fenced_code", "tables", "toc"],
        )

        html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>{PDF_STYLE}</style>
</head>
<body>{html_body}</body>
</html>"""

        safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", generated.repository) or "repository"
        pdf_path = self.config.pdf_dir / f"{safe_name}_documentation.pdf"
        try:
            HTML(string=html).write_pdf(str(pdf_path))
        except Exception as exc:
            logger.exception("PDF generation failed")
            raise RuntimeError(f"Failed to generate PDF: {exc}") from exc

        logger.info("Generated PDF at {}", pdf_path)
        return str(pdf_path)
