from typing import List

from baseline.chess_sql.agents.base import ChessSubAgent
from baseline.chess_sql.state import ChessSQLAgentState
from baseline.utils import (
    extract_json_object,
    is_failed_or_empty_result,
    load_baseline_prompt,
    render_current_time_prompt,
)


class UnitTester(ChessSubAgent):
    """CHESS unit tester: generate unit tests, then evaluate the candidate SQL."""

    def __init__(self, llm, current_time: str) -> None:
        super().__init__(
            llm=llm,
            current_time=current_time,
            name="Unit Tester",
            task="generate natural-language unit tests and evaluate whether the SQL result satisfies them",
        )
        self.generate_unit_tests_prompt = load_baseline_prompt("chess_sql", "generate_unit_tests.md")
        self.evaluate_prompt = load_baseline_prompt("chess_sql", "evaluate.md")
        self.passed = False
        self.evaluated = False
        self.tool_fns = {
            "generate_unit_tests": self.generate_unit_tests,
            "evaluate": self.evaluate,
        }
        self.tool_descriptions = {
            "generate_unit_tests": "Generate semantic unit tests for the candidate SQL.",
            "evaluate": "Evaluate candidate SQL execution result against the unit tests.",
        }

    def is_complete(self, state: ChessSQLAgentState) -> bool:
        return bool(state.unit_tests and self.evaluated)

    async def generate_unit_tests(self, state: ChessSQLAgentState) -> str:
        system_prompt = render_current_time_prompt(self.generate_unit_tests_prompt, state.current_time)
        response = await self.ainvoke(
            system_prompt,
            (
                f"Question:\n{state.user_request or state.question}\n\n"
                f"Selected schema:\n{state.selected_schema}\n\n"
                f"Candidate SQL:\n```sql\n{state.sql_query}\n```"
            ),
            chess_state=state,
            trace_agent="Unit Tester.generate_unit_tests",
        )
        parsed = extract_json_object(response) or {}
        unit_tests = parsed.get("unit_tests", [])
        if not isinstance(unit_tests, list):
            unit_tests = []
        state.unit_tests = [test for test in unit_tests if isinstance(test, str)]
        return f"generate_unit_tests: {state.unit_tests}"

    async def evaluate(self, state: ChessSQLAgentState) -> str:
        if is_failed_or_empty_result(state.sql_result):
            self.passed = False
            self.evaluated = True
            return "evaluate: FAIL empty or failed SQL result"

        system_prompt = render_current_time_prompt(self.evaluate_prompt, state.current_time)
        response = await self.ainvoke(
            system_prompt,
            (
                f"Question:\n{state.user_request or state.question}\n\n"
                f"Unit tests:\n{state.unit_tests}\n\n"
                f"Candidate SQL:\n```sql\n{state.sql_query}\n```\n\n"
                f"Execution result:\n{state.sql_result}"
            ),
            chess_state=state,
            trace_agent="Unit Tester.evaluate",
        )
        parsed = extract_json_object(response) or {}
        self.passed = str(parsed.get("verdict", "")).upper() == "PASS"
        self.evaluated = True
        return f"evaluate: {'PASS' if self.passed else 'FAIL'} {parsed.get('reason', '')}"
