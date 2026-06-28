from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.core.env_config import load_env_config

load_env_config()

from agent.llm import get_llm_wrapper


DEFAULT_MODEL_NAME = os.getenv("MAC_SQL_MODEL") or os.getenv("MODEL_NAME") or "openrouter:openai/gpt-oss-120b"

_WRAPPERS: Dict[str, object] = {}
_LOG_PATH = None
_TRACE_PATH = None


def init_log_path(log_path: str):
    global _LOG_PATH, _TRACE_PATH

    _LOG_PATH = log_path or None
    _TRACE_PATH = None
    if _LOG_PATH:
        log_dir = os.path.dirname(_LOG_PATH)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        _TRACE_PATH = os.path.join(log_dir or ".", "api_trace.jsonl")


def _get_wrapper(model_name: str):
    if model_name not in _WRAPPERS:
        _WRAPPERS[model_name] = get_llm_wrapper(model_name)
    return _WRAPPERS[model_name]


def safe_call_llm(input_prompt: str, model_name: str | None = None, **kwargs) -> str:
    model_name = model_name or kwargs.pop("model_name", None) or DEFAULT_MODEL_NAME
    wrapper = _get_wrapper(model_name)
    response = wrapper(
        messages=[{"role": "user", "content": input_prompt}],
        temperature=0.1,
    )
    if response is None:
        raise RuntimeError(f"LLM returned no response for model {model_name}")
    if not isinstance(response, str):
        response = str(response)

    if _LOG_PATH:
        with open(_LOG_PATH, "a", encoding="utf-8") as log_file:
            log_file.write("\n" + ("*" * 20) + "\n")
            log_file.write(input_prompt)
            log_file.write("\n" + ("=" * 20) + "\n")
            log_file.write(response)
            log_file.write("\n")
        if _TRACE_PATH:
            trace_payload = dict(kwargs)
            trace_payload["model_name"] = model_name
            trace_payload["input_prompt"] = input_prompt
            trace_payload["response"] = response
            try:
                trace_payload["usage"] = wrapper.usage()
            except Exception:
                trace_payload["usage"] = {}
            with open(_TRACE_PATH, "a", encoding="utf-8") as trace_file:
                trace_file.write(json.dumps(trace_payload, ensure_ascii=False) + "\n")

    return response
