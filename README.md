# GitHub Repository Intelligence & Documentation Generator

An AI-powered Flask application that accepts a public GitHub repository URL and
automatically generates professional project documentation as Markdown and PDF.

This is the first module of a larger content creation platform. The generated
`RepositoryKnowledge` object is reusable by future modules such as Blog,
LinkedIn, X Thread, Tutorial, and Presentation generators.

## Features

- Validate public GitHub repository URLs.
- Fetch repository metadata via the GitHub REST API.
- Clone repositories with GitPython.
- Parse README, configuration, dependencies, and source files.
- Ignore generated directories and binary files.
- Infer language, framework, package manager, entry points, and architecture.
- Orchestrate agents with LangGraph.
- Generate full developer documentation with DeepSeek (default) or any OpenAI-compatible provider.
- Export Markdown and styled PDF documents.
- Provide a responsive Tailwind CSS dashboard.

## Architecture

```
Flask UI -> LangGraph workflow -> GitHub fetch -> Parser -> Analyzer ->
Knowledge object -> Documentation generator -> Reviewer -> Markdown/PDF
```

## Requirements

- Python 3.12+
- Git
- WeasyPrint system libraries (see Dockerfile for Debian packages)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `DEEPSEEK_API_KEY` (get it at `https://platform.deepseek.com/api_keys`) and
optionally `GITHUB_TOKEN` in `.env`. The application runs in deterministic mock
mode when no LLM key is configured.

To use any other OpenAI-compatible provider instead, set `LLM_API_KEY`,
`LLM_BASE_URL`, and `LLM_MODEL` (e.g. `LLM_PROVIDER=openai`,
`OPENAI_API_KEY`, and a compatible `LLM_MODEL`, or Groq with `GROQ_API_KEY`
and `https://api.groq.com/openai/v1`).

## Run

```bash
python app.py
```

Open `http://localhost:5000`.

## Tests

```bash
pytest
```

## Deployment

The included `Dockerfile` and `render.yaml` deploy the app to Render with a
single web service. Set `DEEPSEEK_API_KEY` (or `LLM_API_KEY`) and `GITHUB_TOKEN` as Render secrets.
# grow-hack
