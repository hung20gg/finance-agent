import sys
import re
import asyncio
import urllib.parse
from datetime import date
from pathlib import Path
from typing import List, Dict

import streamlit as st
import streamlit.components.v1 as components

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = REPO_ROOT / "agent"
sys.path.insert(0, str(AGENT_ROOT))

try:
    from strategy import get_agent, get_agent_config
    from strategy.bi_agent.state import BIAgentState
    from strategy.text2sql.state import Text2SQLAgentState
    from strategy.text2chart.state import Text2ChartAgentState
except ImportError:
    pass

DEFAULT_MODEL_NAME = "openrouter:qwen/qwen3.5-122b-a10b"
DEFAULT_SQL_URL = "http://localhost:9004/sse"
DEFAULT_MAX_TOOL_CALLS = 10
DEFAULT_SHOW_AGENT_BACKGROUNDS = True

THINK_OPEN_TAG = "<think>"
THINK_CLOSE_TAG = "</think>"

AGENT_AVATARS = {
    "bi_agent": "🤖",
    "text2sql": "🔍",
    "text2chart": "📊",
}


def initialize_session() -> None:
    if "history" not in st.session_state:
        st.session_state.history = []
    if "bi_state" not in st.session_state:
        st.session_state.bi_state = None
    if "show_agent_backgrounds" not in st.session_state:
        st.session_state.show_agent_backgrounds = DEFAULT_SHOW_AGENT_BACKGROUNDS


def create_bi_state(user_request: str) -> "BIAgentState":
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


def render_chart_html(content_val: str) -> None:
    encoded_val = urllib.parse.quote(content_val)
    components.iframe(f"http://localhost:3000/chart?code={encoded_val}", height=500, scrolling=False)


def normalize_markdown_for_display(text: str) -> str:
    """
    Post-process markdown so code fences render nicely.

    Example:
    'Let me create a clean config.```javascript'
    -> 'Let me create a clean config.\n```javascript'
    """
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    result: List[str] = []
    i = 0
    while i < len(text):
        if text.startswith("```", i):
            if result and not result[-1].endswith("\n"):
                result.append("\n")
            result.append("```")
            i += 3
            continue

        result.append(text[i])
        i += 1

    return "".join(result)


def add_stream_cursor(text: str) -> str:
    if not text:
        return "▌"

    # If we are inside an unclosed fenced code block, avoid appending an inline cursor
    # that can make markdown rendering look messy.
    fence_count = len(re.findall(r"```", text))
    if fence_count % 2 == 1:
        return text

    return text + " ▌"


def parse_complete_text_segments(text: str) -> List[Dict[str, str]]:
    segments: List[Dict[str, str]] = []
    pos = 0
    in_think = False

    def append_segment(seg_type: str, content: str) -> None:
        if not content and not (seg_type == "think" and in_think):
            return
        if segments and segments[-1]["type"] == seg_type:
            segments[-1]["content"] += content
        else:
            segments.append({"type": seg_type, "content": content})

    while pos < len(text):
        if not in_think:
            start = text.find(THINK_OPEN_TAG, pos)
            if start == -1:
                append_segment("normal", text[pos:])
                break

            append_segment("normal", text[pos:start])
            pos = start + len(THINK_OPEN_TAG)
            in_think = True
            append_segment("think", "")
        else:
            end = text.find(THINK_CLOSE_TAG, pos)
            if end == -1:
                append_segment("think", text[pos:])
                break

            append_segment("think", text[pos:end])
            pos = end + len(THINK_CLOSE_TAG)
            in_think = False

    return segments


def render_segments(
    segments: List[Dict[str, str]],
    agent_name: str,
    show_background: bool,
    streaming: bool = False,
    open_think_segment_index: int | None = None,
) -> None:
    if show_background:
        st.markdown(
            f"<div class='agent-bg-marker agent-bg-{agent_name}'></div>",
            unsafe_allow_html=True,
        )

    if not segments and streaming:
        st.markdown("▌")
        return

    for idx, segment in enumerate(segments):
        raw_content = segment.get("content", "")
        content = normalize_markdown_for_display(raw_content)
        is_live_segment = streaming and idx == len(segments) - 1

        if segment["type"] == "normal":
            display_text = add_stream_cursor(content) if is_live_segment else content
            if display_text:
                st.markdown(display_text)
        else:
            expanded = idx == open_think_segment_index
            with st.expander("🧠 Thinking", expanded=expanded):
                display_text = add_stream_cursor(content) if is_live_segment else content
                st.markdown(display_text or ("▌" if is_live_segment else ""))


class ThinkStreamRenderer:
    OPEN_TAG = THINK_OPEN_TAG
    CLOSE_TAG = THINK_CLOSE_TAG

    def __init__(self, chat_msg, agent_name: str, show_background: bool):
        self.chat_msg = chat_msg
        self.agent_name = agent_name
        self.show_background = show_background
        self.root_placeholder = chat_msg.empty()

        self.buffer = ""
        self.segments: List[Dict[str, str]] = []
        self.in_think = False

    def _ensure_segment(self, seg_type: str) -> None:
        if not self.segments or self.segments[-1]["type"] != seg_type:
            self.segments.append({"type": seg_type, "content": ""})

    def _append_to_current_segment(self, seg_type: str, text: str) -> None:
        if not text:
            return
        self._ensure_segment(seg_type)
        self.segments[-1]["content"] += text

    def feed(self, text: str) -> None:
        self.buffer += text
        self._parse_incrementally()
        self._render(streaming=True)

    def finalize(self) -> None:
        if self.buffer:
            seg_type = "think" if self.in_think else "normal"
            self._append_to_current_segment(seg_type, self.buffer)
            self.buffer = ""

        self._render(streaming=False)

    def _parse_incrementally(self) -> None:
        while self.buffer:
            if not self.in_think:
                idx = self.buffer.find(self.OPEN_TAG)

                if idx != -1:
                    self._append_to_current_segment("normal", self.buffer[:idx])
                    self.buffer = self.buffer[idx + len(self.OPEN_TAG):]
                    self.in_think = True
                    self._ensure_segment("think")
                    continue

                keep = len(self.OPEN_TAG) - 1
                safe_len = max(0, len(self.buffer) - keep)
                if safe_len > 0:
                    self._append_to_current_segment("normal", self.buffer[:safe_len])
                    self.buffer = self.buffer[safe_len:]
                break

            else:
                idx = self.buffer.find(self.CLOSE_TAG)

                if idx != -1:
                    self._append_to_current_segment("think", self.buffer[:idx])
                    self.buffer = self.buffer[idx + len(self.CLOSE_TAG):]
                    self.in_think = False
                    continue

                keep = len(self.CLOSE_TAG) - 1
                safe_len = max(0, len(self.buffer) - keep)
                if safe_len > 0:
                    self._append_to_current_segment("think", self.buffer[:safe_len])
                    self.buffer = self.buffer[safe_len:]
                break

    def _render(self, streaming: bool) -> None:
        self.root_placeholder.empty()
        with self.root_placeholder.container():
            think_index = len(self.segments) - 1 if streaming and self.in_think else None
            render_segments(
                segments=self.segments,
                agent_name=self.agent_name,
                show_background=self.show_background,
                streaming=streaming,
                open_think_segment_index=think_index,
            )


async def stream_bi_response(agent, state, show_agent_backgrounds: bool):
    message_blocks = []

    current_agent = None
    current_type = None
    current_content = ""

    chat_msg = None
    current_placeholder = None
    think_renderer = None

    async for chunk in agent.astream(state, stream_mode="custom"):
        c_type = chunk.get("type")
        if c_type not in ["content", "chart"]:
            continue

        c_agent = chunk.get("agent", "assistant")
        content_piece = chunk.get(c_type, "")

        if current_agent != c_agent or current_type != c_type:
            if current_agent is not None:
                message_blocks.append(
                    {"agent": current_agent, "type": current_type, "content": current_content}
                )
                if current_type == "content" and think_renderer is not None:
                    think_renderer.finalize()
                elif current_type == "chart" and current_placeholder:
                    current_placeholder.empty()
                    with chat_msg:
                        if show_agent_backgrounds:
                            st.markdown(
                                f"<div class='agent-bg-marker agent-bg-{current_agent}'></div>",
                                unsafe_allow_html=True,
                            )
                        render_chart_html(current_content)

            current_agent = c_agent
            current_type = c_type
            current_content = content_piece

            avatar = AGENT_AVATARS.get(current_agent, "🤖")
            chat_msg = st.chat_message(current_agent, avatar=avatar)
            current_placeholder = None
            think_renderer = None

            if current_type == "content":
                think_renderer = ThinkStreamRenderer(
                    chat_msg=chat_msg,
                    agent_name=current_agent,
                    show_background=show_agent_backgrounds,
                )
                think_renderer.feed(content_piece)
            elif current_type == "chart":
                current_placeholder = chat_msg.empty()
                current_placeholder.markdown("*(Generating chart...)*")

        else:
            current_content += content_piece

            if current_type == "content" and think_renderer is not None:
                think_renderer.feed(content_piece)
            elif current_type == "chart" and current_placeholder:
                current_placeholder.markdown("*(Generating chart...)*")

    if current_agent is not None:
        message_blocks.append(
            {"agent": current_agent, "type": current_type, "content": current_content}
        )
        if current_type == "content" and think_renderer is not None:
            think_renderer.finalize()
        elif current_type == "chart" and current_placeholder:
            current_placeholder.empty()
            with chat_msg:
                if show_agent_backgrounds:
                    st.markdown(
                        f"<div class='agent-bg-marker agent-bg-{current_agent}'></div>",
                        unsafe_allow_html=True,
                    )
                render_chart_html(current_content)

    return message_blocks


def inject_custom_css() -> None:
    st.markdown(
        """
        <style>
        iframe {
            border-radius: 8px;
            border: 1px solid #e0e0e0;
        }

        .agent-bg-marker {
            display: none;
        }

        [data-testid="stChatMessage"] {
            border-radius: 12px;
            padding-top: 0.25rem;
            padding-bottom: 0.25rem;
        }

        [data-testid="stChatMessage"]:has(.agent-bg-text2sql) {
            background-color: rgba(220, 240, 255, 0.55);
        }

        [data-testid="stChatMessage"]:has(.agent-bg-text2chart) {
            background-color: rgba(220, 255, 230, 0.55);
        }

        [data-testid="stChatMessage"]:has(.agent-bg-bi_agent) {
            background-color: rgba(240, 242, 246, 0.7);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Finance BI Agent Chat", layout="wide")
    inject_custom_css()

    st.title("Finance BI Agent Chat")
    st.write("Use the BI agent to ask finance questions and stream responses in real time.")

    initialize_session()

    with st.sidebar:
        st.header("Agent settings")
        model_name = st.text_input("Model name", value=DEFAULT_MODEL_NAME)
        text2sql_url = st.text_input("Text2SQL SSE URL", value=DEFAULT_SQL_URL)
        max_tool_calls = st.number_input(
            "Max tool calls",
            min_value=1,
            max_value=20,
            value=DEFAULT_MAX_TOOL_CALLS,
        )
        show_agent_backgrounds = st.checkbox(
            "Show agent backgrounds",
            value=st.session_state.show_agent_backgrounds,
            help="Color each agent message with its own background.",
        )
        st.session_state.show_agent_backgrounds = show_agent_backgrounds

        if st.button("New conversation"):
            st.session_state.history = []
            st.session_state.bi_state = None
            st.rerun()

    for message in st.session_state.history:
        role = message.get("role", "assistant")
        if role == "user":
            with st.chat_message("user"):
                st.markdown(message.get("content", ""))
        elif role == "assistant":
            blocks = message.get("blocks", [])
            for block in blocks:
                agent_name = block["agent"]
                avatar = AGENT_AVATARS.get(agent_name, "🤖")
                with st.chat_message(agent_name, avatar=avatar):
                    if block["type"] == "content":
                        render_segments(
                            segments=parse_complete_text_segments(block["content"]),
                            agent_name=agent_name,
                            show_background=show_agent_backgrounds,
                            streaming=False,
                        )
                    elif block["type"] == "chart":
                        if show_agent_backgrounds:
                            st.markdown(
                                f"<div class='agent-bg-marker agent-bg-{agent_name}'></div>",
                                unsafe_allow_html=True,
                            )
                        render_chart_html(block["content"])

    if user_request := st.chat_input("Ask a finance question"):
        if st.session_state.bi_state is None:
            st.session_state.bi_state = create_bi_state(user_request)
        else:
            st.session_state.bi_state.user_request = user_request
            st.session_state.bi_state.current_time = date.today().isoformat()

        st.session_state.history.append({"role": "user", "content": user_request})

        with st.chat_message("user"):
            st.markdown(user_request)

        config = build_agent_config(
            model_name=model_name,
            sql_url=text2sql_url,
            max_tool_calls=max_tool_calls,
        )
        agent = get_agent(config)

        with st.spinner("Agent thinking..."):
            run_async(agent.initialize())

        assistant_blocks = run_async(
            stream_bi_response(
                agent,
                st.session_state.bi_state,
                show_agent_backgrounds=show_agent_backgrounds,
            )
        )
        st.session_state.history.append({"role": "assistant", "blocks": assistant_blocks})


if __name__ == "__main__":
    main()
