"""Provider adapters. Credentials are read only when their provider is used."""

import os
import time
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Reply:
    text: str
    provider: str
    model: str
    latency_s: float
    finish_reason: str
    usage: dict


def complete(system, user, temperature=0.7, max_tokens=900, seed=42, json_mode=True):
    provider = os.getenv("LLM_PROVIDER", "ollama")
    model = os.getenv("LLM_MODEL") or {
        "ollama": "qwen2.5:7b",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-haiku-4-5",
    }.get(provider, "")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    start = time.perf_counter()
    if provider == "ollama":
        payload = dict(
            model=model,
            messages=messages,
            stream=False,
            options=dict(temperature=temperature, seed=seed, num_predict=max_tokens, num_ctx=4096),
        )
        if json_mode:
            payload["format"] = "json"
        response = requests.post(
            os.getenv("OLLAMA_URL", "http://127.0.0.1:11434") + "/api/chat", json=payload, timeout=(10, 240)
        )
        response.raise_for_status()
        data = response.json()
        raw = data["message"]["content"]
        reason = data.get("done_reason", "unknown")
        usage = {key: data.get(key) for key in ["prompt_eval_count", "eval_count"]}
    elif provider == "openai":
        from openai import OpenAI

        kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
        data = OpenAI(timeout=240, max_retries=0).chat.completions.create(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, **kwargs
        )
        raw = data.choices[0].message.content or ""
        reason = data.choices[0].finish_reason
        usage = data.usage.model_dump() if data.usage else {}
    elif provider == "anthropic":
        from anthropic import Anthropic

        data = Anthropic(timeout=240, max_retries=0).messages.create(
            model=model, system=system, messages=[messages[1]], temperature=temperature, max_tokens=max_tokens
        )
        raw = "".join(block.text for block in data.content if block.type == "text")
        reason, usage = data.stop_reason, data.usage.model_dump()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
    return Reply(raw, provider, model, round(time.perf_counter() - start, 3), reason, usage)
