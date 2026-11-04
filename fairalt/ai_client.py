"""The only place that talks to the AI model.

Every other module calls ask(prompt, image_path) and gets a dict back.

Providers (set AI_PROVIDER in .env):
  claude_code - Claude through the Claude Code CLI, using your Claude
            subscription login; no API key (CLAUDE_MODEL, CLAUDE_EFFORT,
            optional CLAUDE_CODE_BIN)
  anthropic - Claude API (ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_EFFORT)
  openai  - OpenAI API (OPENAI_API_KEY, OPENAI_MODEL)
  azure   - Azure OpenAI (AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
            AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION)
  mock    - offline scripted answers for testing the pipeline and UI
"""
import base64
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
PROMPTS = ROOT / "prompts"

load_dotenv(ROOT / ".env")

_lock = threading.Lock()
_local = threading.local()  # per-thread usage, so each question gets its own tokens and cost
_client = None
_send_temperature = True
USAGE = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}


def provider():
    return os.getenv("AI_PROVIDER", "mock").strip().lower()


def model_name():
    p = provider()
    if p in ("anthropic", "claude_code"):
        return os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
    if p == "azure":
        return os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
    if p == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4o")
    return "mock"


def reset_usage():
    with _lock:
        USAGE.update(calls=0, prompt_tokens=0, completion_tokens=0)


def _record(calls, prompt_tokens=0, completion_tokens=0):
    with _lock:
        for u in (USAGE, getattr(_local, "usage", None)):
            if u is not None:
                u["calls"] += calls
                u["prompt_tokens"] += prompt_tokens
                u["completion_tokens"] += completion_tokens


def start_tracking():
    """Start counting usage for this thread only (one question)."""
    _local.usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}


def current_tracking():
    """The usage counter of this thread, to hand to helper threads."""
    return getattr(_local, "usage", None)


def use_tracking(counter):
    """Count this thread's calls into another thread's counter (see current_tracking)."""
    _local.usage = counter


def tracked_usage():
    """Usage on this thread since start_tracking(), with estimated cost."""
    return _with_cost(dict(getattr(_local, "usage", None) or {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}))


def usage_summary():
    """Usage so far, plus an estimated cost if prices are set in .env."""
    with _lock:
        u = dict(USAGE)
    return _with_cost(u)


def _with_cost(u):
    price_in = float(os.getenv("PRICE_IN_PER_1M", "0") or 0)
    price_out = float(os.getenv("PRICE_OUT_PER_1M", "0") or 0)
    u["est_cost_usd"] = round(
        u["prompt_tokens"] / 1e6 * price_in + u["completion_tokens"] / 1e6 * price_out, 4
    )
    return u


def load_prompt(name, **values):
    """Read prompts/<name>.txt and fill {placeholders}.

    Uses plain replace rather than str.format so the JSON braces in the
    prompts are left alone.
    """
    text = (PROMPTS / f"{name}.txt").read_text(encoding="utf-8")
    for key, val in values.items():
        if not isinstance(val, str):
            val = json.dumps(val, ensure_ascii=False)
        text = text.replace("{" + key + "}", val)
    return text


def parse_json(text):
    """Parse a model reply as JSON, tolerating code fences and extra prose."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _get_client():
    global _client
    if _client is not None:
        return _client
    p = provider()
    if p == "anthropic":
        import anthropic

        # Reads ANTHROPIC_API_KEY (or an `ant auth login` profile).
        _client = anthropic.Anthropic()
        return _client

    from openai import AzureOpenAI, OpenAI

    if p == "azure":
        _client = AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        )
    elif p == "openai":
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    else:
        raise ValueError(f"Unknown AI_PROVIDER: {p!r} (use claude_code, anthropic, openai, azure or mock)")
    return _client


def _image_base64(image_path):
    path = Path(image_path)
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return mime, base64.standard_b64encode(path.read_bytes()).decode("ascii")


def _claude_content(prompt, image_path):
    """The message content for Claude: the image first when there is one, then the prompt."""
    content = []
    if image_path:
        mime, data = _image_base64(image_path)
        content.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}})
    content.append({"type": "text", "text": prompt})
    return content


# Models that accept the server-side refusal fallback on the Claude API.
_CLAUDE_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}


def _complete_claude(prompt, image_path, model=None):
    """One Claude call; returns the reply text.

    Current Claude models reject temperature, so it is not sent; how hard
    the model thinks is set with CLAUDE_EFFORT (low | medium | high).
    """
    content = _claude_content(prompt, image_path)

    model = model or model_name()
    kwargs = dict(
        model=model,
        max_tokens=16000,
        output_config={"effort": os.getenv("CLAUDE_EFFORT", "medium")},
        messages=[{"role": "user", "content": content}],
    )
    if model in _CLAUDE_FALLBACK_MODELS:
        # If a safety classifier declines, the API retries on a fallback model.
        kwargs.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    resp = _get_client().beta.messages.create(**kwargs)

    _record(1, resp.usage.input_tokens or 0, resp.usage.output_tokens or 0)
    if resp.stop_reason == "refusal":
        raise ValueError("Claude declined this request")
    if resp.stop_reason == "max_tokens":
        raise ValueError("Claude's reply was cut off (max_tokens)")
    return "".join(b.text for b in resp.content if b.type == "text")


_CLAUDE_CODE_SYSTEM = (
    "You answer exactly as the user's instructions ask. Reply with the requested JSON only, "
    "with no other text."
)
_empty_dir = None


def _claude_code_bin():
    found = os.getenv("CLAUDE_CODE_BIN") or shutil.which("claude") or os.getenv("CLAUDE_CODE_EXECPATH")
    if not found:
        raise RuntimeError(
            "Claude Code CLI not found. Install it, or set CLAUDE_CODE_BIN in .env to the claude binary."
        )
    return found


def _complete_claude_code(prompt, image_path, model=None):
    """One call through `claude -p`, signed in with the user's Claude subscription.

    All tools are switched off, so the model sees only what is in the
    message: Student B cannot open the image file. The image, when given,
    is sent inside the message like an API call would send it.
    """
    global _empty_dir
    with _lock:
        if _empty_dir is None:
            # Run outside the project so no CLAUDE.md or project settings are picked up.
            _empty_dir = tempfile.mkdtemp(prefix="fairalt_")

    content = _claude_content(prompt, image_path)
    message = json.dumps({"type": "user", "message": {"role": "user", "content": content}})

    cmd = [
        _claude_code_bin(), "-p",
        "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
        "--tools", "", "--strict-mcp-config", "--no-session-persistence",
        "--system-prompt", _CLAUDE_CODE_SYSTEM,
        "--model", model or model_name(),
        "--effort", os.getenv("CLAUDE_EFFORT", "medium"),
    ]
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)  # use the subscription login, not a stray key
    proc = subprocess.run(cmd, input=message + "\n", capture_output=True, text=True,
                          cwd=_empty_dir, env=env, timeout=600)

    result = None
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "result":
            result = event
    if result is None:
        raise RuntimeError(f"Claude Code gave no result (exit {proc.returncode}): {proc.stderr.strip()[-400:]}")
    if result.get("is_error"):
        raise RuntimeError(f"Claude Code error: {result.get('result') or result.get('subtype')}")

    u = result.get("usage") or {}
    _record(1, sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
            u.get("output_tokens") or 0)
    return result.get("result") or ""


def _complete(content, temperature, model=None):
    """One OpenAI/Azure chat call; drops temperature if the model refuses it."""
    global _send_temperature
    from openai import BadRequestError

    kwargs = dict(
        model=model or model_name(),
        messages=[{"role": "user", "content": content}],
        response_format={"type": "json_object"},
    )
    if _send_temperature and temperature is not None:
        kwargs["temperature"] = temperature
    try:
        resp = _get_client().chat.completions.create(**kwargs)
    except BadRequestError as e:
        if "temperature" in str(e).lower() and "temperature" in kwargs:
            _send_temperature = False
            kwargs.pop("temperature")
            resp = _get_client().chat.completions.create(**kwargs)
        else:
            raise
    _record(1, (resp.usage.prompt_tokens or 0) if resp.usage else 0,
            (resp.usage.completion_tokens or 0) if resp.usage else 0)
    return resp.choices[0].message.content


def ask(prompt, image_path=None, temperature=0.0, model=None):
    """Send a prompt (and optionally an image) and return the parsed JSON dict.

    model overrides the configured model for this call (e.g. a smaller
    model for Student B). Retries once if the reply is not valid JSON.
    """
    if provider() == "mock":
        import mock_ai

        _record(1)
        return mock_ai.respond(prompt, image_path)

    if provider() == "claude_code":
        call = lambda: _complete_claude_code(prompt, image_path, model)
    elif provider() == "anthropic":
        call = lambda: _complete_claude(prompt, image_path, model)
    else:
        content = [{"type": "text", "text": prompt}]
        if image_path:
            mime, data = _image_base64(image_path)
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}})
        call = lambda: _complete(content, temperature, model)

    last_error = None
    for _ in range(2):
        reply = call()
        try:
            return parse_json(reply)
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
    raise ValueError(f"Model did not return valid JSON: {last_error}")
