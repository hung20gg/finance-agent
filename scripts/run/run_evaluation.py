from transformers import AutoTokenizer
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
import datasets
from typing import Any, Dict, List, Union
import traceback



from reward_function import compute_score
from env_config import load_env_config, get_env
# Load environment configuration
load_env_config()

# Add agent path to sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from agent.strategy import get_agent_state, get_agent, get_agent_config

model_id = "Qwen/Qwen3-4B"
tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)

OpenAIMessage = Dict[str, Any]
HFMessage = Dict[str, str]

def flatten_openai_messages(messages: List[OpenAIMessage]) -> List[HFMessage]:
    """
    Convert OpenAI 'content as list of blocks' into HF 'content as str'.
    - Keeps roles: system/user/assistant/tool
    - For content blocks: concatenates only text blocks.
    - If content is already a string, keeps it.
    - Preserves tool_calls (assistant) and tool_call_id (tool) for chat templates.
    """
    out: List[HFMessage] = []

    for m in messages:
        role = m.get("role")
        content = m.get("content")  # may be None for tool-calling assistant messages

        # Case 1: already a string (or None → empty string)
        if content is None:
            text = ""
        elif isinstance(content, str):
            text = content

        # Case 2: OpenAI blocks: [{"type":"text","text":"..."}, ...]
        elif isinstance(content, list):
            parts = []
            for blk in content:
                if isinstance(blk, dict) and blk.get("type") == "text":
                    parts.append(blk.get("text", ""))
                # If you have images/audio/etc, either skip or add a placeholder:
                # elif blk.get("type") == "image_url": parts.append("[image]")
            text = "".join(parts)

        # Fallback
        else:
            text = str(content)

        msg: HFMessage = {"role": role, "content": text}

        # Preserve tool_calls for assistant messages (needed by chat templates)
        if "tool_calls" in m and m["tool_calls"]:
            msg["tool_calls"] = m["tool_calls"]

        # Preserve tool_call_id for tool-response messages
        if "tool_call_id" in m:
            msg["tool_call_id"] = m["tool_call_id"]

        out.append(msg)

    return out


def initialize_agent(args) -> tuple[Any, Any]:
    
    agent_type = args.agent_type
    base_model = args.base_model
    current_time = '2025-12-31'
    remove_think_tag = args.hint

    if not remove_think_tag:
        if 'train' not in args.input_file  and 'vllm' not in base_model.lower():
            remove_think_tag = True

    if remove_think_tag:
        print("Think tag will be removed from agent response for evaluation. If you want to keep think tag, please use train flag or use a vLLM model for evaluation")

    agent_config = {
        "agent_type": agent_type,
        "model_name": base_model,
        "streaming": False,
        "urls" : ["http://localhost:9004/sse"],
        "max_tool_calls": 15,
        "remove_think_tag": remove_think_tag,
    }

    state_config = {
        "agent_type": agent_type, 
        "current_time": current_time
    }
    print(agent_config)

    state = get_agent_state(**state_config)
    agent_config = get_agent_config(**agent_config)

    agent = get_agent(config=agent_config)
    
    return agent, state



async def run_evaluation(question: dict, output_file: str, args: argparse.Namespace, write_lock: asyncio.Lock):

    question_id = question.get("id")

    if question_id is None:
        return
    
    agent, state = initialize_agent(args)
    await agent.initialize()

    if "question" not in question:
        return

    print(json.dumps(question.get("question", ""), ensure_ascii=False, indent=2))

    answer_type = question.get("answer_type", "text")
    question_str = question.get("question", "") + f" [{answer_type}]"

    if answer_type == "tuple":
        expected_columns = question.get("extra_info", {}).get("result_columns", [])
        if not expected_columns:
            # Fallback: derive expected columns from answer dict keys
            ans = question.get("answer", {})
            if isinstance(ans, dict):
                expected_columns = list(ans.keys())
        if expected_columns:
            question_str += f" (Expected columns: {', '.join(expected_columns)})"

    if args.hint:
        question_str = question.get("question_raw", "") + f" [{answer_type}]"

        entities = question.get("entities", [])
        metrics = question.get("metrics", [])
        clues = question.get("extra_info", {})
        answer_str = str(question.get("answer", ""))

        question_str += f"\n\nHere is some hint that might help you answer the question:\n\nEntities: {', '.join(entities)}\n\nMetrics: {', '.join(metrics)}\n\nClues: {json.dumps(clues, ensure_ascii=False, indent=2)}"
        if 'yoy' in question_str.lower():
            question_str += "\n\nNote that yoy means year over year, and you need to get data for both year and do calculation"
        if 'qoq' in question_str.lower():
            question_str += "\n\nNote that qoq means quarter over quarter, and you need to get data for both quarter and do calculation"

        question_str += f"\n\nAnswer: {answer_str}\n\nYou must generate the SQL that have similar answer with the answer above. IF not, you should return -100 to signal that you are unable to generate"

    state.user_request = question_str

    # update_state = None
    try:
        update_state = await agent.ainvoke(state)
    except Exception as exc:
        print(f"Error during agent invocation for question_id={question_id}: {exc}")
        update_state = state  # Use the last known state even if invocation fails


    messages = update_state.messages
        
    hf_messages = flatten_openai_messages(messages)

    flatten_messages = tokenizer.apply_chat_template(
        hf_messages,
        tokenize=False,
    )

    ground_truth = question['answer']
    try:
        score = compute_score(
            flatten_messages,
            ground_truth,
        )
    except Exception as exc:
        
        print(f"Error computing score for question_id={question_id}: {exc}")
        
        score = {
            "total_score": 0.0,
            "error": str(exc),
        }

    print('## Finished evaluation for question_id={question_id} with score={score}'.format(
        question_id=question_id,
        score=score,
    ))
    async with write_lock:
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                "id": question_id,
                "score": score,
                "messages": messages[1:],
            }, ensure_ascii = False) + '\n')


def load_processed_question_ids(output_file: str) -> list[dict]:
    
    if not os.path.exists(output_file):
        return []
    
    with open(output_file, 'r', encoding='utf-8') as f:
        questions = []
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                qid = json.loads(line).get('id')
            except json.JSONDecodeError:
                continue
            if qid is not None:
                questions.append(qid)
    return questions


def load_questions(output_file: str) -> list[dict]:
    
    if not os.path.exists(output_file):
        return []
    
    with open(output_file, 'r', encoding='utf-8') as f:
        questions = []
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                q = json.loads(line)
                # if q.get('answer_type') != 'tuple':
                #     continue
            except json.JSONDecodeError:
                continue
            questions.append(q)
    return questions


def load_questions_for_evaluation(args) -> list[dict]:

    processed_questions = load_processed_question_ids(args.output_file)
    
    # For Hugging Face datasets, we can load directly from the dataset path
    # dataset = datasets.load_dataset(args.dataset_path, split=args.split)

    dataset = load_questions(args.input_file)



    questions = [
        question
        for question in dataset
        if question.get('id') not in processed_questions
    ]
    
    print(f"Loaded {len(questions)} questions for evaluation (skipped {len(processed_questions)} already processed)")
    
    return questions
    
async def run_evaluation_on_dataset(args):
    questions = load_questions_for_evaluation(args)

    semaphore = asyncio.Semaphore(args.num_worker)
    write_lock = asyncio.Lock()

    async def sem_run(question):
        async with semaphore:
            try:
                await run_evaluation(question, args.output_file, args, write_lock)
            except Exception as e:
                print(f"[SKIP] Question failed: {question}")
                print(f"Error: {e}")
                traceback.print_exc()

    await asyncio.gather(*[sem_run(q) for q in questions])
    
# async def run_evaluation_on_dataset(args):
#     questions = load_questions_for_evaluation(args)

#     for question in questions:
#         await run_evaluation(question,  args.output_file, args, asyncio.Lock())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_file", type=str, required=True)
    parser.add_argument("--output_file", type=str, required=True)
    parser.add_argument("--agent_type", type=str, default="text2sql")
    parser.add_argument("--base_model", type=str, required=True)
    parser.add_argument("--num_worker", type=int, default=1)
    parser.add_argument("--hint", action="store_true")
    args = parser.parse_args()
    asyncio.run(run_evaluation_on_dataset(args))