"""Flask application entry point for the GitHub Documentation generator."""

from __future__ import annotations

import re

from flask import Flask, jsonify, render_template, request, send_file

from agents.content_agent import ContentAgent
from agents.graph import DocumentationGraph
from config import get_config
from services.cover_service import build_title_card_html, read_logo_file, render_title_card_png, upload_to_catbox
from services.devto_service import DevToError, DevToService
from services.github_service import GitHubError
from services.image_service import generate_image_url
from services.logging_service import setup_logging

config = get_config()
setup_logging(config)

app = Flask(__name__)
app.config["SECRET_KEY"] = config.secret_key
app.config["JSON_SORT_KEYS"] = False

documentation_graph = DocumentationGraph(config)
content_agent = ContentAgent(config)
devto_service = DevToService(config)


@app.get("/")
def index():
    """Render the landing page with the repository input form."""
    return render_template("index.html")


@app.post("/analyze")
def analyze():
    """Analyze a GitHub repository and return generated artifacts.

    Returns:
        JSON containing summary, documentation, markdown, and PDF download
        endpoints. On failure, returns an error object with a 400 status.
    """
    payload = request.get_json(silent=True) or {}
    repo_url = payload.get("repo_url", "").strip()

    if not repo_url:
        return jsonify({"error": "Repository URL is required."}), 400

    try:
        result = documentation_graph.run(repo_url)
    except GitHubError as exc:
        return jsonify({"error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"error": f"Repository data not found: {exc}"}), 400
    except Exception as exc:  # noqa: BLE001 - surface unexpected errors to UI
        return jsonify({"error": f"Analysis failed: {exc}"}), 500

    generated = result.get("generated")
    if generated is None:
        return jsonify({"error": "No documentation was generated."}), 500

    summary = generated.summary
    summary["markdown_path"] = generated.markdown_path
    summary["pdf_path"] = result.get("pdf_path", "")
    summary["pdf_available"] = bool(result.get("pdf_path"))

    return jsonify(
        {
            "summary": summary,
            "documentation": generated.documentation_markdown,
            "readme": generated.readme_markdown,
            "markdown": generated.markdown_path,
            "pdf": result.get("pdf_path", ""),
        }
    )


@app.post("/generate-content")
def generate_content():
    """Generate publish-ready content from a topic or repository input.

    Returns:
        JSON matching the content OUTPUT CONTRACT: input_type,
        interpreted_as, title, content_markdown, image_prompts,
        notes_for_judge, plus the saved markdown path.
    """
    payload = request.get_json(silent=True) or {}
    input_text = payload.get("input", "").strip()

    if not input_text:
        return jsonify({"error": "Content input is required."}), 400

    try:
        result = content_agent.run(input_text)
    except Exception as exc:  # noqa: BLE001 - surface unexpected errors to UI
        return jsonify({"error": f"Content generation failed: {exc}"}), 500

    title = (result.get("title") or "Generated Content").strip()
    safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", title)[:80] or "generated-content"
    markdown_path = config.content_dir / f"{safe_name}.md"
    markdown_path.write_text(result.get("content_markdown") or "", encoding="utf-8")
    result["markdown_path"] = str(markdown_path)

    publish_article(result)

    return jsonify(result)


def publish_article(result: dict) -> None:
    """Publish the generated article to Dev.to, never crashing the request.

    On success the live ``devto_url`` is merged into the result; on any
    failure a clear ``publish_error`` is set so the frontend can show
    "generated but not published: <reason>".
    """
    if not devto_service.is_configured():
        result["publish_error"] = "Dev.to API key not configured."
        return

    image_prompts = result.get("image_prompts") or []
    main_image = None
    cover_image = build_cover_image(result)
    if cover_image:
        main_image = cover_image
        result["cover_image"] = cover_image
    elif image_prompts:
        try:
            main_image = generate_image_url(image_prompts[0])
            if main_image:
                result["cover_image"] = main_image
        except Exception:  # noqa: BLE001 - cover image is a bonus, never fatal
            main_image = None

    try:
        published = devto_service.publish(
            title=result.get("title") or "Generated Content",
            body_markdown=result.get("content_markdown") or "",
            tags=result.get("tags") or [],
            main_image=main_image,
        )
    except DevToError as exc:
        result["publish_error"] = str(exc)
        return
    except Exception as exc:  # noqa: BLE001 - publishing must never crash the request
        result["publish_error"] = f"Unexpected publish failure: {exc}"
        return

    result["devto_url"] = published.get("url", "")


def build_cover_image(result: dict) -> str | None:
    """Render an HTML title-card cover (with repo logo when available) and host it.

    Falls back to None so the caller can try the Pollinations URL instead.
    """
    title = result.get("title") or ""
    if not title:
        return None
    try:
        logo_bytes, logo_mime = read_logo_file(result.get("cover_logo_path"))
        card_html = build_title_card_html(
            title=title,
            subtitle=result.get("interpreted_as") or result.get("input_type") or "",
            tags=result.get("tags") or [],
            logo_bytes=logo_bytes,
            logo_mime=logo_mime,
            author=result.get("cover_author") or config.author_name,
        )
        png = render_title_card_png(card_html)
        if not png:
            return None
        return upload_to_catbox(png)
    except Exception:  # noqa: BLE001 - cover images are best-effort
        return None


@app.get("/download/markdown")
def download_markdown():
    """Serve the generated Markdown file for download."""
    path = request.args.get("path", "")
    if not path:
        return jsonify({"error": "Markdown path is required."}), 400
    try:
        return send_file(path, as_attachment=True, download_name="documentation.md")
    except FileNotFoundError:
        return jsonify({"error": "Markdown file not found."}), 404


@app.get("/download/pdf")
def download_pdf():
    """Serve the generated PDF file for download."""
    path = request.args.get("path", "")
    if not path:
        return jsonify({"error": "PDF path is required."}), 400
    try:
        return send_file(path, as_attachment=True, download_name="documentation.pdf")
    except FileNotFoundError:
        return jsonify({"error": "PDF file not found."}), 404


if __name__ == "__main__":
    app.run(host=config.host, port=config.port, debug=config.flask_env == "development")
