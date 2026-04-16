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

EVALUATE_MODEL = "openrouter:qwen/qwen3.5-122b-a10b"

def initialize_agent(agent_type: str, base_model: str, self_evaluation: bool, chart_type: str, current_time: str = "2025-12-31"):
    
    agent_config = {
        "agent_type": agent_type,
        "model_name": base_model,
        "self_evaluation": self_evaluation,
        "streaming": False,
        "urls" : ["http://localhost:9004/sse"],
        "max_tool_calls": 9,
        "chart_type": chart_type,
    }

    state_config = {
        "agent_type": agent_type, 
        "current_time": current_time
    }

    state = get_agent_state(**state_config)
    agent_config = get_agent_config(**agent_config)

    agent = get_agent(config=agent_config)
    
    return agent, state



async def compute_score(prediction, ground_truth) -> int:

    evaluate_agent, evaluate_state = initialize_agent("chart_evaluator", EVALUATE_MODEL, True, "matplotlib", '2025-12-31')
    await evaluate_agent.initialize()

    evaluate_state.user_request = f"Dataset detail \n{ground_truth}"

    evaluate_state.chart_generation = prediction

    update_state = await evaluate_agent.ainvoke(evaluate_state)

    return update_state.chart_evaluation.score




async def run_evaluation(question: dict, output_file: str, args, write_lock: asyncio.Lock):

    question_id = question.get("id")

    if question_id is None:
        return
    
    if args.self_evaluation:
        self_evaluation = True
    else:
        self_evaluation = False

    print(f'## Starting evaluation for question_id={question_id} with self_evaluation={self_evaluation}')

    agent, state = initialize_agent("text2chart", args.base_model, self_evaluation, args.chart_type, '2025-12-31')
    await agent.initialize()

    

    if "question" not in question:
        return

    print(json.dumps(question.get("question", ""), ensure_ascii=False, indent=2))

    answer_type = question.get("answer_type", "text")
    question_str = question.get("question", "")
    ground_truth = question['answer']

    if "vẽ" not in question_str:
        question_str += "\n\nYêu cầu: Vẽ biểu đồ dựa trên dữ liệu được cung cấp."

    # question_str += f"\n\nData for generation:\n{ground_truth}"

    state.user_request = question_str

    state.data = ground_truth


    # update_state = None
    try:
        update_state = await agent.ainvoke(state)
    except Exception as exc:
        print(f"Error during agent invocation for question_id={question_id}: {exc}")
        update_state = state  # Use the last known state even if invocation fails


    messages = update_state.messages

    print(messages[1:])
        

    ground_truth = question['answer']
    try:
        score = await compute_score(
            update_state.chart_generation,
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

                # Only load questions that have answer_type 'tuple' for chart evaluation
                if q.get('answer_type') != 'tuple':
                    continue
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
    parser.add_argument("--chart_type", type=str, default="matplotlib")
    parser.add_argument("--base_model", type=str, required=True)
    parser.add_argument("--num_worker", type=int, default=1)
    parser.add_argument("--self_evaluation", action="store_true")
    args = parser.parse_args()
    asyncio.run(run_evaluation_on_dataset(args))


    

    
    

