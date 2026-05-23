"""Thin provider-agnostic LLM client wrapper.

Supports two providers: OpenAI and Google Gemini. Model IDs are passed as `provider:model`,
e.g. `openai:gpt-4o`, `gemini:gemini-2.5-pro`, or `groq:llama-3.3-70b-versatile`.

Features:
  - Auto-loads ``.env`` at import time (no python-dotenv dependency).
  - Simple file-based response cache to avoid repeating expensive calls during dev.
  - One automatic retry on transient errors.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path


# ---------- env loading ----------------------------------------------------

def _load_dotenv() -> None:
    """Load .env from project root if present. Safe to call multiple times."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        return


_load_dotenv()


# ---------- cache ----------------------------------------------------------

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".llm_cache"


# ---------- gentle inter-request pacing -----------------------------------

# Spaces non-cached requests by at least this many seconds to avoid bursting through
# free-tier rate limits. ETS makes many calls in a tight loop and was triggering 429s
# on both Groq and Gemini free tiers.
_MIN_INTER_REQUEST_SECONDS = 0.6
_last_call_ts: dict[str, float] = {}


def _wait_for_rate_pace(provider: str) -> None:
    now = time.time()
    last = _last_call_ts.get(provider, 0.0)
    gap = now - last
    if gap < _MIN_INTER_REQUEST_SECONDS:
        time.sleep(_MIN_INTER_REQUEST_SECONDS - gap)
    _last_call_ts[provider] = time.time()


def _cache_path(provider: str, model: str, prompt: str, temperature: float) -> Path:
    key = f"{provider}|{model}|{temperature:.2f}|{prompt}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:32]
    return _CACHE_DIR / f"{provider}-{model.replace('/', '_')}-{digest}.json"


# ---------- response type --------------------------------------------------

@dataclass
class LLMResponse:
    provider: str
    model: str
    text: str
    cached: bool = False
    raw: object | None = None


def parse_model_id(model_id: str) -> tuple[str, str]:
    provider, _, model = model_id.partition(":")
    if not model:
        raise ValueError(f"Expected provider:model, got {model_id!r}")
    return provider, model


# ---------- retry helpers --------------------------------------------------

_RETRY_AFTER_RE = re.compile(r"(?:retry[\- ]after[: =]+|Please try again in )(\d+(?:\.\d+)?)\s*(s|ms|second|seconds)?", re.IGNORECASE)


def _wait_from_error(exc: Exception, attempt: int) -> float:
    """Pick a backoff in seconds. Honors Retry-After when present, else exponential."""
    msg = str(exc)
    m = _RETRY_AFTER_RE.search(msg)
    if m:
        val = float(m.group(1))
        unit = (m.group(2) or "s").lower()
        seconds = val / 1000.0 if unit == "ms" else val
        return min(60.0, max(1.0, seconds + 0.5))
    # Exponential: 2, 6, 14, 30
    return min(30.0, 2 * (2 ** attempt) - 2)


# ---------- providers ------------------------------------------------------

def _complete_openai(model: str, prompt: str, temperature: float, max_tokens: int) -> str:
    from openai import OpenAI  # local import keeps import-time cost low

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set (check .env)")
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def _complete_groq(model: str, prompt: str, temperature: float, max_tokens: int) -> str:
    from groq import Groq

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set (check .env)")
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def _complete_gemini(model: str, prompt: str, temperature: float, max_tokens: int) -> str:
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set (check .env)")
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )
    return resp.text or ""


# ---------- public API -----------------------------------------------------

def complete(
    model_id: str,
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    use_cache: bool = True,
) -> LLMResponse:
    """Single-turn completion. Caches responses by (provider, model, prompt, temperature)."""
    provider, model = parse_model_id(model_id)

    if use_cache:
        path = _cache_path(provider, model, prompt, temperature)
        if path.is_file():
            data = json.loads(path.read_text())
            return LLMResponse(provider=provider, model=model, text=data["text"], cached=True)

    last_err: Exception | None = None
    text: str = ""
    succeeded = False
    for attempt in range(4):
        try:
            _wait_for_rate_pace(provider)
            if provider == "openai":
                text = _complete_openai(model, prompt, temperature, max_tokens)
            elif provider == "gemini":
                text = _complete_gemini(model, prompt, temperature, max_tokens)
            elif provider == "groq":
                text = _complete_groq(model, prompt, temperature, max_tokens)
            else:
                raise ValueError(f"Unknown provider: {provider!r}")
            succeeded = True
            break
        except Exception as exc:
            last_err = exc
            # Parse Retry-After-style hints from the error message; default exponential.
            wait = _wait_from_error(exc, attempt)
            if attempt < 3:
                time.sleep(wait)
    if not succeeded:
        assert last_err is not None
        raise last_err

    if use_cache:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _cache_path(provider, model, prompt, temperature)
        path.write_text(json.dumps({"text": text, "model": model, "provider": provider}))

    return LLMResponse(provider=provider, model=model, text=text, cached=False)
