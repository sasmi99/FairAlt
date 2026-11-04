"""Checks the Claude request and reply handling against a local stand-in server.

Uses the real anthropic SDK, so no API key or network is needed.
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ai_client

captured = {}


def _reply(text, stop_reason="end_turn"):
    return {
        "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": [{"type": "thinking", "thinking": "", "signature": "sig"}, {"type": "text", "text": text}],
        "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 120, "output_tokens": 30},
    }


class Handler(BaseHTTPRequestHandler):
    reply = _reply('{"answer": "2", "reasoning": "rise 6 over run 3"}')

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        captured["path"] = self.path
        captured["body"] = json.loads(body)
        captured["beta"] = self.headers.get("anthropic-beta")
        out = json.dumps(Handler.reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


@pytest.fixture
def claude(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("CLAUDE_MODEL", "claude-opus-5-5")
    monkeypatch.setenv("CLAUDE_EFFORT", "medium")
    monkeypatch.setattr(ai_client, "_client", None)
    ai_client.reset_usage()
    yield
    server.shutdown()
    ai_client._client = None


def test_claude_request_with_image_and_json_reply(claude):
    image = ROOT / "data" / "images" / "q01_slope.png"
    result = ai_client.ask("Answer. Return JSON only.", image, temperature=0.0)

    assert result == {"answer": "2", "reasoning": "rise 6 over run 3"}
    body = captured["body"]
    assert body["model"] == "claude-opus-5-5"
    assert "temperature" not in body                      # rejected by current Claude models
    assert body["output_config"] == {"effort": "medium"}
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in captured["beta"]
    content = body["messages"][0]["content"]
    assert content[0]["type"] == "image" and content[0]["source"]["media_type"] == "image/png"
    assert content[1] == {"type": "text", "text": "Answer. Return JSON only."}
    u = ai_client.usage_summary()
    assert (u["calls"], u["prompt_tokens"], u["completion_tokens"]) == (1, 120, 30)


def test_claude_text_only_and_fenced_json(claude, monkeypatch):
    monkeypatch.setattr(Handler, "reply", _reply('```json\n{"status": "GREEN"}\n```'))
    assert ai_client.ask("Judge. Return JSON only.") == {"status": "GREEN"}
    assert [c["type"] for c in captured["body"]["messages"][0]["content"]] == ["text"]


def test_claude_refusal_raises(claude, monkeypatch):
    monkeypatch.setattr(Handler, "reply", _reply("", stop_reason="refusal"))
    with pytest.raises(ValueError, match="declined"):
        ai_client.ask("x")


def test_model_override_for_student_b(claude):
    """A smaller model can be used for one call (Student B); usage still counts."""
    ai_client.ask("Answer. Return JSON only.", model="claude-haiku-5-5")
    body = captured["body"]
    assert body["model"] == "claude-haiku-5-5"
    assert "fallbacks" not in body                        # only sent for models that support it
    assert ai_client.usage_summary()["calls"] == 1
