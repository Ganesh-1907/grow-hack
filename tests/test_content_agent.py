"""Tests for the Content Production Agent (no network or LLM required)."""

from __future__ import annotations

import json

from config import Config
from agents.content_agent import ContentAgent, detect_language, extract_json_object


class FakeLLMService:
    """In-memory LLM stub returning a canned contract for the draft pass."""

    _client = object()

    def __init__(self, response: str) -> None:
        self.response = response

    def complete(self, prompt, temperature=0.2, system_prompt=None):
        return self.response


class FakeGitHubAgent:
    """Stub that raises on fetch so repo failure paths are testable."""

    def run(self, repo_url: str):
        raise RuntimeError("simulated fetch failure")


def make_agent(llm_response: str) -> ContentAgent:
    config = Config(enable_mock_llm=False)
    return ContentAgent(config, llm_service=FakeLLMService(llm_response), github_agent=FakeGitHubAgent())


def sample_contract() -> dict:
    return {
        "input_type": "topic",
        "interpreted_as": "covered as a tutorial",
        "title": "Building a REST API",
        "content_markdown": "# Building a REST API\n\nFull body here.",
        "image_prompts": [],
        "notes_for_judge": "Sampled nothing.",
    }


def test_classify_repo_url() -> None:
    agent = make_agent("{}")
    assert agent.classify_input("https://github.com/octocat/Hello-World") == "repo"
    assert agent.classify_input("https://gitlab.com/group/project") == "repo"


def test_classify_repo_code_snapshot() -> None:
    agent = make_agent("{}")
    snapshot = "package.json\napp.js\nsrc/index.js"
    assert agent.classify_input(snapshot) == "repo"


def test_classify_topic() -> None:
    agent = make_agent("{}")
    assert agent.classify_input("how do I deploy a FastAPI app to Render?") == "topic"


def test_classify_ambiguous() -> None:
    agent = make_agent("{}")
    assert agent.classify_input("") == "ambiguous"
    assert agent.classify_input("   ") == "ambiguous"
    assert agent.classify_input("langgraph") == "ambiguous"


def test_detect_language() -> None:
    assert detect_language("hello world") == "English"
    assert detect_language("नमस्ते दुनिया") == "Hindi"
    assert detect_language("你好世界") == "Chinese"
    assert detect_language("Привет мир") == "Russian"


def test_extract_json_object_from_noisy_text() -> None:
    assert extract_json_object('prefix {"a": 1} suffix') == {"a": 1}
    assert extract_json_object("no json here") == {}


def test_parse_fenced_contract() -> None:
    contract = sample_contract()
    agent = make_agent("")
    parsed = agent._parse_contract("```json\n" + json.dumps(contract) + "\n```")
    assert parsed["title"] == contract["title"]
    assert parsed["input_type"] == "topic"


def test_parse_broken_output_falls_back() -> None:
    agent = make_agent("")
    parsed = agent._parse_contract("this is not json at all")
    assert parsed["title"] == "Generated Content"
    assert parsed["content_markdown"] == "this is not json at all"
    assert parsed["image_prompts"] == []
    assert "not valid JSON" in parsed["notes_for_judge"]


def test_run_returns_contract_with_real_llm() -> None:
    contract = sample_contract()
    agent = make_agent(json.dumps(contract))
    result = agent.run("how do I build a REST API?")
    assert result["title"] == "Building a REST API"
    assert result["input_type"] == "topic"
    assert result["content_markdown"].startswith("# Building a REST API")


def test_run_llm_failure_still_returns_contract() -> None:
    class ExplodingLLM:
        _client = object()

        def complete(self, prompt, temperature=0.2, system_prompt=None):
            raise RuntimeError("provider down")

    config = Config(enable_mock_llm=False)
    agent = ContentAgent(config, llm_service=ExplodingLLM(), github_agent=FakeGitHubAgent())
    result = agent.run("some topic here")
    assert result["input_type"] == "topic"
    assert result["title"] == "Generated Content"
    assert result["content_markdown"]  # never empty


def test_repo_fetch_failure_writes_honest_note() -> None:
    contract = sample_contract()
    agent = make_agent(json.dumps(contract))
    result = agent.run("https://github.com/octocat/Hello-World")
    assert "could not be fetched" in result["notes_for_judge"]
