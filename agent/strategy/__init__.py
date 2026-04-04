import sys
from pathlib import Path

# Load environment config before any other imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'core'))
from env_config import load_env_config
load_env_config()

from core.agent import BaseAgentMCP, BaseAgentMCPConfig
from .react.agent import ReActAgent, ReActAgentConfig
from .react.state import ReActAgentState
from .text2sql.agent import Text2SQLAgent, Text2SQLAgentConfig
from .text2sql.state import Text2SQLAgentState
from .text2chart.agent import Text2ChartAgent, Text2ChartAgentConfig
from .text2chart.state import Text2ChartAgentState
from .bi_agent.agent import BIAgent, BIAgentConfig
from .bi_agent.state import BIAgentState

from typing import Union, Optional

def get_agent_config(agent_type: str, **kwargs) -> Union[ReActAgentConfig, Text2SQLAgentConfig, Text2ChartAgentConfig, BIAgentConfig]:
    if agent_type == "react":
        return ReActAgentConfig(**kwargs)
    elif agent_type == "text2sql":
        return Text2SQLAgentConfig(**kwargs)
    elif agent_type == "text2chart":
        return Text2ChartAgentConfig(**kwargs)
    elif agent_type == "bi_agent":
        return BIAgentConfig(**kwargs)

    else:
        raise ValueError(f"Unknown agent type: {agent_type}")

def get_agent(config: BaseAgentMCPConfig) -> Union[ReActAgent, Text2SQLAgent, Text2ChartAgent, BIAgent  ]:
    if config.agent_type == "react":
        return ReActAgent(config=config)
    elif config.agent_type == "text2sql":
        return Text2SQLAgent(config=config)
    elif config.agent_type == "text2chart":
        return Text2ChartAgent(config=config)
    elif config.agent_type == "bi_agent":
        return BIAgent(config=config)
    else:
        raise ValueError(f"Unknown agent config")
    
def get_agent_state(agent_type: str, **kwargs) -> Optional[type]:
    if agent_type == "react":
        return ReActAgentState(**kwargs)
    elif agent_type == "text2sql":
        return Text2SQLAgentState(**kwargs)
    elif agent_type == "text2chart":
        return Text2ChartAgentState(**kwargs)
    elif agent_type == "bi_agent":
        text2sql_state_config = kwargs.pop("text2sql_state_config", {}) or {}
        text2chart_state_config = kwargs.pop("text2chart_state_config", {}) or {}
        text2sql_state_config.pop("agent_type", None)
        text2chart_state_config.pop("agent_type", None)
        text2sql_state = Text2SQLAgentState(**text2sql_state_config)
        text2chart_state = Text2ChartAgentState(**text2chart_state_config)
        return BIAgentState(
            text2sql_state=text2sql_state,
            text2chart_state=text2chart_state,
            **kwargs
        )
    else:
        return None

__all__ = ["ReActAgent", "Text2SQLAgent", "Text2ChartAgent", "BIAgent", "get_agent", "get_agent_config", "get_agent_state"]