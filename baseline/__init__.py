from typing import Any, Dict

from baseline.vanilla import VanillaAgent, VanillaAgentConfig, VanillaAgentState


BASELINE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "vanilla": {
        "agent": VanillaAgent,
        "config": VanillaAgentConfig,
        "state": VanillaAgentState,
    },
}


def _normalize_method(method: str) -> str:
    return method.strip().lower()


def get_baseline_config(method: str, **kwargs):
    method = _normalize_method(method)
    if method not in BASELINE_REGISTRY:
        raise ValueError(f"Unknown baseline method: {method}")
    return BASELINE_REGISTRY[method]["config"](**kwargs)


def get_baseline_state(method: str, **kwargs):
    method = _normalize_method(method)
    if method not in BASELINE_REGISTRY:
        raise ValueError(f"Unknown baseline method: {method}")
    return BASELINE_REGISTRY[method]["state"](**kwargs)


def get_baseline(method: str, config):
    method = _normalize_method(method)
    if method not in BASELINE_REGISTRY:
        raise ValueError(f"Unknown baseline method: {method}")
    return BASELINE_REGISTRY[method]["agent"](config=config)
