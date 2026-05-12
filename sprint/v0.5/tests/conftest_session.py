"""tests/conftest_session.py — fixtures for session-aware tests.

Drop into tests/conftest.py (merge with existing) so that test_sandbox_sessions,
test_browser_sessions, test_react_executor get a clean session root + isolated
artifact DB per test.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def sandbox_session_root(tmp_path, monkeypatch):
    """Isolate sandbox session storage to a per-test tmp dir."""
    root = tmp_path / "sandbox-sessions"
    root.mkdir()
    monkeypatch.setenv("RASPUTIN_OMNITOOL_SESSION_ROOT", str(root))
    # Force a fresh singleton
    import agent.session_manager as sm
    sm._INSTANCE = None
    yield root
    sm._INSTANCE = None


@pytest.fixture
def browser_session_root(tmp_path, monkeypatch):
    """Isolate browser session storage to a per-test tmp dir."""
    root = tmp_path / "browser-sessions"
    root.mkdir()
    monkeypatch.setenv("RASPUTIN_OMNITOOL_BROWSER_SESSION_ROOT", str(root))
    try:
        import agent.browser_session as bs
        bs._INSTANCE = None
    except ImportError:
        pass
    yield root
    try:
        import agent.browser_session as bs
        bs._INSTANCE = None
    except ImportError:
        pass


@pytest.fixture
def checkpoint_root(tmp_path, monkeypatch):
    """Isolate checkpoint storage."""
    root = tmp_path / "checkpoints"
    root.mkdir()
    monkeypatch.setenv("RASPUTIN_OMNITOOL_CHECKPOINT_ROOT", str(root))
    yield root


@pytest.fixture
def artifact_db(tmp_path, monkeypatch):
    """Isolate artifact registry to a per-test SQLite file."""
    db = tmp_path / "artifacts.db"
    monkeypatch.setenv("RASPUTIN_OMNITOOL_ARTIFACT_DB", str(db))
    try:
        import agent.artifact_registry as ar
        ar._INSTANCE = None
    except ImportError:
        pass
    yield db
    try:
        import agent.artifact_registry as ar
        ar._INSTANCE = None
    except ImportError:
        pass


@pytest.fixture
def outputs_dir(tmp_path, monkeypatch):
    """Direct all tool outputs to a per-test dir."""
    d = tmp_path / "outputs"
    d.mkdir()
    monkeypatch.setenv("RASPUTIN_OMNITOOL_OUTPUTS_DIR", str(d))
    yield d


@pytest.fixture
def fake_llm(monkeypatch):
    """Mock the OpenAI client used by react_executor.

    Usage:
        def test_x(fake_llm):
            fake_llm.set_responses([
                {"tool_call": {"name": "crawl4ai", "args": {"url": "..."}}},
                {"final": "done"},
            ])
            run_goal(...)
    """
    class _FakeLLM:
        def __init__(self):
            self.responses: list[dict] = []
            self.calls: list[dict] = []

        def set_responses(self, responses):
            self.responses = list(responses)

        def __call__(self, *args, **kwargs):
            self.calls.append({"args": args, "kwargs": kwargs})
            if not self.responses:
                raise RuntimeError("fake_llm out of responses")
            return self._build_response(self.responses.pop(0))

        @staticmethod
        def _build_response(spec: dict):
            # Mirror the OpenAI chat completion shape minimally.
            from types import SimpleNamespace
            import json as _json
            import uuid

            if "final" in spec:
                msg = SimpleNamespace(content=spec["final"], tool_calls=None)
                choice = SimpleNamespace(message=msg, finish_reason="stop")
            else:
                tc = SimpleNamespace(
                    id=f"call_{uuid.uuid4().hex[:8]}",
                    function=SimpleNamespace(
                        name=spec["tool_call"]["name"],
                        arguments=_json.dumps(spec["tool_call"].get("args", {})),
                    ),
                )
                msg = SimpleNamespace(content=spec.get("content", ""), tool_calls=[tc])
                choice = SimpleNamespace(message=msg, finish_reason="tool_calls")
            return SimpleNamespace(
                choices=[choice],
                usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50),
            )

    fake = _FakeLLM()
    # Patch the OpenAI client used by react_executor.
    # Adjust the patch target to match the actual import path in your project.
    monkeypatch.setattr("agent.react_executor.OpenAI", lambda **kw: type(
        "FakeClient", (), {
            "chat": type("FakeChat", (), {
                "completions": type("FakeComp", (), {"create": fake})()
            })()
        }
    )())
    return fake
