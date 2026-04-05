# Finance BI Agent - Streamlit Application

This directory contains the Streamlit web application interface for the LangGraph-based Finance BI Agent. The application acts as an interactive chat to stream multi-agent responses dynamically. 

## Main Features

1. **Multi-Agent Streaming Interface**: 
   - Dynamically processes text chunks (`type="content"`) and JavaScript configurations (`type="chart"`).
   - Colors agent chat boxes differently when switching from one sub-agent to another, giving you maximum visibility into which agent (e.g. `bi_agent`, `text2sql`, `text2chart`) is currently planning or executing.
   
2. **Chart Rendering**: 
   - Seamlessly generates Highcharts visuals during a conversation.
   - Inject the streamed chart JS configuration seamlessly into the `template.html` to visualize data within the chat stream as an HTML component block.

3. **Multi-turn Context tracking**:
   - Conversations are kept inside the session history object, and messages are rendered as stylized blocks.
   
4. **Agent Configurations**:
   - Easily swap out settings, models (default is set to OpenRouter's `qwen3.5-122b-a10b`), text2SQL addresses, or maximum tool calls dynamically by accessing the sidebar settings.

## How to Run

1. Make sure you have your environment set up and the necessary configurations loaded (refer to top level documentation inside `AGENTS.md`).

2. Start the MCP server first (in the `mcp-server` directory). The Streamlit app relies on SSE logic being available here:
   ```bash
   cd mcp-server
   python -m src.server
   ```

3. Open a new terminal and start the Streamlit application:
   ```bash
   cd streamlit
   streamlit run app.py
   ```
   *Note: Ensure your `agent` packages/dependencies are installed since the internal stream runs directly through `agent.core` and `strategy` folders.*

## Usage Workflow

1. Open the app link provided by Streamlit (usually `http://localhost:8501`).
2. Tweak settings in the sidebar (Model Name, SSE URL) if needed.
3. In the text area at the bottom labeled "Ask a finance question", type your query (e.g., *Vẽ biểu đồ lợi nhuận VIC 2025*).
4. Watch as the interface streams intermediate agent steps iteratively with distinct background colors representing the agent thinking!
5. View custom Highcharts visualizations instantly inside the browser.
