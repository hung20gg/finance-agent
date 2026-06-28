from typing import Any, Dict, List

from baseline.chess_sql.agents.base import ChessSubAgent
from baseline.chess_sql.state import ChessSQLAgentState
from baseline.utils import extract_json_object, load_baseline_prompt, render_current_time_prompt


class InformationRetriever(ChessSubAgent):
    """CHESS information retriever: extract keywords, retrieve entities, retrieve context."""

    def __init__(self, llm, current_time: str) -> None:
        super().__init__(
            llm=llm,
            current_time=current_time,
            name="Information Retriever",
            task="retrieve useful question evidence by calling extract_keywords, retrieve_entity, and retrieve_context",
        )
        self.extract_keywords_prompt = load_baseline_prompt("chess_sql", "extract_keywords.md")
        self.retrieve_entity_prompt = load_baseline_prompt("chess_sql", "retrieve_entity.md")
        self.retrieve_context_prompt = load_baseline_prompt("chess_sql", "retrieve_context.md")
        self.tool_fns = {
            "extract_keywords": self.extract_keywords,
            "retrieve_entity": self.retrieve_entity,
            "retrieve_context": self.retrieve_context,
        }
        self.tool_descriptions = {
            "extract_keywords": "Extract task keywords from the user question.",
            "retrieve_entity": "Infer likely database entities and identifier candidates from keywords.",
            "retrieve_context": "Write compact task evidence for downstream SQL generation.",
        }

    def is_complete(self, state: ChessSQLAgentState) -> bool:
        return bool(state.keywords and state.retrieved_entities and state.retrieved_context)

    async def extract_keywords(self, state: ChessSQLAgentState) -> str:
        system_prompt = render_current_time_prompt(self.extract_keywords_prompt, state.current_time)
        response = await self.ainvoke(
            system_prompt,
            f"Question:\n{state.user_request or state.question}",
            chess_state=state,
            trace_agent="Information Retriever.extract_keywords",
        )
        parsed = extract_json_object(response) or {}
        keywords = parsed.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = []
        state.keywords = [keyword for keyword in keywords if isinstance(keyword, str)]
        return f"extract_keywords: {state.keywords}"

    async def retrieve_entity(self, state: ChessSQLAgentState) -> str:
        system_prompt = render_current_time_prompt(self.retrieve_entity_prompt, state.current_time)
        response = await self.ainvoke(
            system_prompt,
            (
                f"Question:\n{state.user_request or state.question}\n\n"
                f"Keywords:\n{state.keywords}"
            ),
            chess_state=state,
            trace_agent="Information Retriever.retrieve_entity",
        )
        parsed = extract_json_object(response) or {}
        state.retrieved_entities = parsed
        return f"retrieve_entity: {state.retrieved_entities}"

    async def retrieve_context(self, state: ChessSQLAgentState) -> str:
        system_prompt = render_current_time_prompt(self.retrieve_context_prompt, state.current_time)
        state.retrieved_context = await self.ainvoke(
            system_prompt,
            (
                f"Question:\n{state.user_request or state.question}\n\n"
                f"Keywords:\n{state.keywords}\n\n"
                f"Retrieved entities:\n{state.retrieved_entities}"
            ),
            chess_state=state,
            trace_agent="Information Retriever.retrieve_context",
        )
        return f"retrieve_context: {state.retrieved_context}"
