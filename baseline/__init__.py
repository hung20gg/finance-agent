from typing import Any, Dict

from baseline.chase_sql.agent import ChaseSQLAgent, ChaseSQLAgentConfig
from baseline.chase_sql.state import ChaseSQLAgentState
from baseline.chess_sql.agent import ChessSQLAgent, ChessSQLAgentConfig
from baseline.chess_sql.state import ChessSQLAgentState
from baseline.e_sql.agent import ESQLAgent, ESQLAgentConfig
from baseline.e_sql.state import ESQLAgentState
from baseline.din_sql.agent import DINSQLAgent, DINSQLAgentConfig
from baseline.din_sql.state import DINSQLAgentState
from baseline.mac_sql.agent import MacSQLAgent, MacSQLAgentConfig
from baseline.mac_sql.state import MacSQLAgentState
from baseline.vanilla import VanillaAgent, VanillaAgentConfig, VanillaAgentState


BASELINE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "vanilla": {
        "agent": VanillaAgent,
        "config": VanillaAgentConfig,
        "state": VanillaAgentState,
    },
    "chess_sql": {
        "agent": ChessSQLAgent,
        "config": ChessSQLAgentConfig,
        "state": ChessSQLAgentState,
    },
    "chase_sql": {
        "agent": ChaseSQLAgent,
        "config": ChaseSQLAgentConfig,
        "state": ChaseSQLAgentState,
    },
    "e_sql": {
        "agent": ESQLAgent,
        "config": ESQLAgentConfig,
        "state": ESQLAgentState,
    },
    "mac_sql": {
        "agent": MacSQLAgent,
        "config": MacSQLAgentConfig,
        "state": MacSQLAgentState,
    },
    "din_sql": {
        "agent": DINSQLAgent,
        "config": DINSQLAgentConfig,
        "state": DINSQLAgentState,
    }
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
