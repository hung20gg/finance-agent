from langgraph.graph import StateGraph, START, END
from langgraph.config import get_stream_writer
import os
from typing import Dict, Any, AsyncIterable, Optional
import re


from core.agent import BaseAgentMCP, BaseAgentMCPConfig, conditional_weave_op
from core.logger import logger
from .state import Text2ChartAgentState
from .utils import render_highchart_image, render_matplotlib_image, extract_critique_and_score


current_dir = os.path.dirname(os.path.abspath(__file__))
chart_system_prompt_path_matplotlib = os.path.join(current_dir, '..', "..", "prompt", "text2chart_system_prompt_matplotlib.md")
chart_system_prompt_path_highchart = os.path.join(current_dir, '..', "..", "prompt", "text2chart_system_prompt_highchart.md")


chart_evaluation_prompt_path = os.path.join(current_dir, '..', "..", "prompt", "text2chart_evaluation_system_prompt.md")

with open(chart_system_prompt_path_matplotlib, "r", encoding="utf-8") as file:
    TEXT2CHART_SYSTEM_PROMPT_MATPLOTLIB = file.read()

with open(chart_system_prompt_path_highchart, "r", encoding="utf-8") as file:
    TEXT2CHART_SYSTEM_PROMPT_HIGHCHART = file.read()

with open(chart_evaluation_prompt_path, "r", encoding="utf-8") as file:
    TEXT2CHART_EVALUATION_PROMPT= file.read()


class Text2ChartAgentConfig(BaseAgentMCPConfig):
    agent_type: str = "text2chart" # or chart_evaluator
    chart_type: str = "highchart"  # or "matplotlib"
    self_evaluation: bool = False
    max_tool_calls: int = 10
    save_charts: bool = False  # Whether to save generated charts to disk
    evaluation_model_name: Optional[str] = None  # Optionally specify a different model for evaluation


def code_block_extractor(text: str) -> str:
    """
    Extract code block from the given text. Assumes code block is enclosed in triple backticks ``` and optionally followed by a language identifier.
    """
    code_block_pattern = r"```(?:\w+)?\n(.*?)```"
    match = re.search(code_block_pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
        return text.strip()  # Return original text if no code block is found

class Text2ChartAgent(BaseAgentMCP[Text2ChartAgentState, Text2ChartAgentConfig]):
    
    def __init__(self, config: Text2ChartAgentConfig) -> None:
        super().__init__(config=config)
        self.state_class = Text2ChartAgentState
        if self.config.self_evaluation:
            if self.config.evaluation_model_name:
                self.evaluation_llm = self.initialize_llm(self.config.evaluation_model_name)
            else:
                self.evaluation_llm = self.llm  # Use the same LLM for evaluation if no separate model is specified

    @staticmethod
    def clear_previous_task_state(state: Text2ChartAgentState) -> Text2ChartAgentState:

        state.current_iteration = 0
        state.chart_generation = ''
        state.chart_evaluation = None
        state.chart_rendering = ''
        state.total_tokens = 0
        state.total_prompt_tokens = 0
        state.total_output_tokens = 0
        
        return state

    @conditional_weave_op(call_display_name="Text2Chart Generation")
    async def generate_chart(self, state: Text2ChartAgentState) -> Text2ChartAgentState:
        
        system_prompt = TEXT2CHART_SYSTEM_PROMPT_MATPLOTLIB if self.config.chart_type == "matplotlib" else TEXT2CHART_SYSTEM_PROMPT_HIGHCHART

        if len(state.messages) == 0:
            state.messages.append(
                {
                    "role": "system",
                    "content": system_prompt.replace(
                        "[current_time]", state.current_time
                        )
                }
            )
        if state.messages[0]['role'] != 'system':
            state.messages.insert(0,
                {
                    "role": "system",
                    "content": system_prompt.replace(
                        "[current_time]", state.current_time
                        )
                }
            )

        if state.current_iteration == 0:

            state = self.clear_previous_task_state(state)

            
            state.messages.append(
                {
                    "role": "user",
                    "content": f"{state.user_request}\n\nData: {str(state.data)}"
                }
            )

        logger.info(f"Invoking Text2Chart Agent, iteration {state.current_iteration + 1}")
        state.current_iteration += 1
        
        # Invoke evaluation LLM with the evaluation messages
        result = await self.llm_ainvoke(state.messages, state=state)
        state.messages.append({
            "role": "assistant",
            "content": result
        })
        
        # Extract code block from the result
        extracted_chart_code = code_block_extractor(result)
        state.chart_generation = extracted_chart_code
        if self.streaming:
            stream_writer = get_stream_writer()
            stream_writer({'type': 'chart', 'chart': extracted_chart_code, 'agent': self.config.agent_type})
        
        # logger.info(f"Text2Chart Agent result: {result}")
        
        return state
    
    def render_chart(self, chart_generation: str) -> Any:
        if self.config.chart_type == "highchart":
            return render_highchart_image(chart_generation)
        
        elif self.config.chart_type == "matplotlib":
            return render_matplotlib_image(chart_generation)

    @conditional_weave_op(call_display_name="Text2Chart Evaluation")
    async def evaluate_chart(self, state: Text2ChartAgentState) -> Text2ChartAgentState:
        evaluation_prompt = TEXT2CHART_EVALUATION_PROMPT
        
        rendered_image = self.render_chart(state.chart_generation)

        if self.config.save_charts:
            os.makedirs(f"tmp/generated_charts/{self.config.chart_type}", exist_ok=True)
            logger.info(f"Saving generated chart for iteration {state.current_iteration} to tmp/generated_charts/{self.config.chart_type}/chart_iter_{state.current_iteration}.png")
            rendered_image.save(f"tmp/generated_charts/{self.config.chart_type}/chart_iter_{state.current_iteration}.png")

        evaluation_messages = [
            {
                "role": "system",
                "content": evaluation_prompt
            },
            {
                'role': 'user',
                'content': [
                    {
                        "type": "text",
                        "text": f"Please evaluate the following chart based on the user's request: {state.user_request}. Here is the data {state.data}" 
                    },
                    {
                        "type": "image",
                        "image": rendered_image
                    }
                ]
            }
        ]
        
        # Invoke evaluation LLM with the evaluation messages
        result = await self.llm_ainvoke(evaluation_messages, state=state)
        
        evaluation_feedback = extract_critique_and_score(result)
        
        logger.info(f"Self-evaluation result: {evaluation_feedback.score}")
        state.chart_evaluation = evaluation_feedback
        
        return state


    @conditional_weave_op(call_display_name="Finalize React Agent State")
    async def finalize(self, state: Text2ChartAgentState) -> Text2ChartAgentState:

        state.current_iteration = 0  # Reset iteration for next invocation
        return await super().finalize(state)


    def build_quick_graph(self) -> StateGraph:

        workflow = StateGraph(Text2ChartAgentState)

        workflow.add_node("generate_chart", self.generate_chart)
        workflow.add_node("finalize", self.finalize)

        workflow.set_entry_point("generate_chart")
        workflow.add_edge("generate_chart", "finalize")
        workflow.add_edge("finalize", END)
        graph = workflow.compile()

        return graph
    
    def build_evaluator_graph(self) -> StateGraph:

        workflow = StateGraph(Text2ChartAgentState)

        workflow.add_node("evaluate_chart", self.evaluate_chart)
        workflow.add_node("finalize", self.finalize)

        workflow.set_entry_point("evaluate_chart")
        workflow.add_edge("evaluate_chart", "finalize")
        workflow.add_edge("finalize", END)
        
        graph = workflow.compile()

        return graph

    def is_regenerate_chart_needed(self, state: Text2ChartAgentState) -> str:
        # Check if the chart generation is finished or if we need to regenerate
        if state.chart_generation is None:
            return 'true'  # No chart generated yet, need to generate

        if state.current_iteration >= self.config.max_tool_calls:
            return 'false'  # Reached maximum iterations, do not regenerate
        
        if state.chart_evaluation is not None and state.chart_evaluation.score >= 4.0:
            return 'false'  # Chart is good enough, do not regenerate

        # Additional logic can be added here to determine if regeneration is needed based on evaluation results or other criteria
        return 'false'  # Default to not regenerating if a chart has already been generated

    def build_self_evaluation_graph(self) -> StateGraph:

        workflow = StateGraph(Text2ChartAgentState)

        workflow.add_node("generate_chart", self.generate_chart)
        workflow.add_node("evaluate_chart", self.evaluate_chart)
        workflow.add_node("finalize", self.finalize)

        workflow.set_entry_point("generate_chart")
        workflow.add_edge("generate_chart", "evaluate_chart")
        workflow.add_edge("generate_chart", "evaluate_chart")
        workflow.add_conditional_edges(
            "evaluate_chart",
            self.is_regenerate_chart_needed,
            {
                'true': "generate_chart",
                'false': "finalize"
            }
        )

        workflow.add_edge("finalize", END)
        
        graph = workflow.compile()

        return graph

    def build_graph(self) -> StateGraph:

        if self.config.agent_type == "chart_evaluator":
            return self.build_evaluator_graph()

        if self.config.self_evaluation:
            return self.build_self_evaluation_graph()
        else:
            return self.build_quick_graph()

    @conditional_weave_op(call_display_name="Invoke Text2Chart Agent")
    async def ainvoke(self, state: Text2ChartAgentState) -> Text2ChartAgentState:
        return await super().ainvoke(state)
    
    @conditional_weave_op(call_display_name="Stream Text2Chart Agent")
    async def astream(self, state: Text2ChartAgentState, stream_mode="custom") -> AsyncIterable[Dict[str, Any]]:
        async for chunk in super().astream(state, stream_mode=stream_mode):
            yield chunk
