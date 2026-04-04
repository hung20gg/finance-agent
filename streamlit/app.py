import sys
import asyncio
from datetime import date
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = REPO_ROOT / "agent"
sys.path.insert(0, str(AGENT_ROOT))

from strategy import get_agent, get_agent_config
from strategy.bi_agent.state import BIAgentState
from strategy.text2sql.state import Text2SQLAgentState
from strategy.text2chart.state import Text2ChartAgentState

DEFAULT_MODEL_NAME = "openrouter:qwen/qwen3.5-122b-a10b"
DEFAULT_SQL_URL = "http://localhost:9004/sse"
DEFAULT_MAX_TOOL_CALLS = 10


def initialize_session() -> None:
    if "history" not in st.session_state:
        st.session_state.history = []
    if "bi_state" not in st.session_state:
        st.session_state.bi_state = None
    if "user_input" not in st.session_state:
        st.session_state.user_input = ""
    if "last_response" not in st.session_state:
        st.session_state.last_response = ""


def create_bi_state(user_request: str) -> BIAgentState:
    current_time = date.today().isoformat()
    return BIAgentState(
        current_time=current_time,
        user_request=user_request,
        text2sql_state=Text2SQLAgentState(current_time=current_time),
        text2chart_state=Text2ChartAgentState(current_time=current_time),
    )


def build_agent_config(model_name: str, sql_url: str, max_tool_calls: int):
    text2sql_agent_config = {
        "agent_type": "text2sql",
        "streaming": True,
        "model_name": model_name,
        "urls": [sql_url] if sql_url else [],
    }
    text2chart_agent_config = {
        "agent_type": "text2chart",
        "streaming": True,
        "model_name": model_name,
        "urls": [],
    }
    return get_agent_config(
        agent_type="bi_agent",
        streaming=True,
        model_name=model_name,
        urls=[sql_url] if sql_url else [],
        max_tool_calls=max_tool_calls,
        text2sql_agent_config=text2sql_agent_config,
        text2chart_agent_config=text2chart_agent_config,
    )


def run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            asyncio.set_event_loop(None)


async def stream_bi_response(agent, state, output_container, log_container):
    assistant_content = ""
    async for chunk in agent.stream(state, stream_mode="custom"):
        if chunk.get("type") == "content":
            assistant_content += chunk.get("content", "")
            output_container.markdown(assistant_content)
        elif chunk.get("type") == "log":
            log_container.text(chunk.get("log", ""))
    return assistant_content


def main() -> None:
    st.set_page_config(page_title="Finance BI Agent Chat", layout="wide")
    st.title("Finance BI Agent Chat")
    st.write("Use the BI agent to ask finance questions and stream responses in real time.")

    initialize_session()

    with st.sidebar:
        st.header("Agent settings")
        model_name = st.text_input("Model name", value=DEFAULT_MODEL_NAME)
        text2sql_url = st.text_input("Text2SQL SSE URL", value=DEFAULT_SQL_URL)
        max_tool_calls = st.number_input("Max tool calls", min_value=1, max_value=20, value=DEFAULT_MAX_TOOL_CALLS)
        if st.button("New conversation"):
            st.session_state.history = []
            st.session_state.bi_state = None
            st.session_state.last_response = ""
            st.session_state.user_input = ""

    if st.session_state.history:
        for message in st.session_state.history:
            role = message.get("role", "assistant")
            content = message.get("content", "")
            if hasattr(st, "chat_message"):
                with st.chat_message(role):
                    st.markdown(content)
            else:
                prefix = "You:" if role == "user" else "Agent:"
                st.markdown(f"**{prefix}** {content}")

    with st.form(key="bi_agent_form", clear_on_submit=False):
        user_request = st.text_area("Ask a finance question", value=st.session_state.user_input, key="user_input", height=120)
        submit = st.form_submit_button("Send")

    if submit and user_request.strip():
        if st.session_state.bi_state is None:
            st.session_state.bi_state = create_bi_state(user_request)
        else:
            st.session_state.bi_state.user_request = user_request
            st.session_state.bi_state.current_time = date.today().isoformat()

        st.session_state.history.append({"role": "user", "content": user_request})

        config = build_agent_config(model_name=model_name, sql_url=text2sql_url, max_tool_calls=max_tool_calls)
        agent = get_agent(config)

        with st.spinner("Initializing agent and streaming response..."):
            run_async(agent.initialize())
            output_container = st.empty()
            log_container = st.empty()
            assistant_response = run_async(stream_bi_response(agent, st.session_state.bi_state, output_container, log_container))

        st.session_state.history.append({"role": "assistant", "content": assistant_response})
        st.session_state.last_response = assistant_response
        st.session_state.user_input = ""

        st.experimental_rerun()

    if st.session_state.last_response and not submit:
        st.markdown("---")
        st.subheader("Last answer")
        st.markdown(st.session_state.last_response)


if __name__ == "__main__":
    main()
