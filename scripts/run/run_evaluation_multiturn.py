import argparse
import asyncio
import json
import os
import sys
import traceback
from pathlib import Path
from transformers import AutoTokenizer

from env_config import load_env_config
load_env_config()

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from agent.strategy import get_agent_state, get_agent, get_agent_config
from agent.strategy.bi_agent.const import TEXT2SQL_TOOL_NAME, TEXT2CHART_TOOL_NAME

def fix_and_load_json(file_path):
    # Try to load as standard JSON first
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Fallback to load dirty JSON using regex or line-by-line if it's JSONL
    # For now, try splitting by {"id": to extract sessions manually if needed
    import re
    sessions = []
    
    # Add commas between objects if missing
    text_fixed = re.sub(r'\}\s*\{', '}, {', text)
    # Fix unescaped newlines in strings
    def escape_newlines(match):
        return match.group(0).replace('\n', '\\n')
    text_fixed = re.sub(r'\"(.*?)\"', escape_newlines, text_fixed, flags=re.DOTALL)
    
    try:
        return json.loads(text_fixed, strict=False)
    except Exception as e:
        print(f"Failed to parse JSON dataset: {e}")
        # As a last resort, parse line by line (if it actually is JSONL)
        sessions_lines = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    sessions_lines.append(json.loads(line))
                except:
                    continue
        if sessions_lines:
            return sessions_lines
        raise ValueError(f"Could not parse dataset at {file_path}")

def flatten_openai_messages(messages):
    out = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")

        if content is None:
            text = ""
        elif isinstance(content, str):
            text = content
        elif isinstance(content, list):
            parts = []
            for blk in content:
                if isinstance(blk, dict) and blk.get("type") == "text":
                    parts.append(blk.get("text", ""))
            text = "".join(parts)
        else:
            text = str(content)

        msg = {"role": role, "content": text}
        if "tool_calls" in m and m["tool_calls"]:
            msg["tool_calls"] = m["tool_calls"]
        if "tool_call_id" in m:
            msg["tool_call_id"] = m["tool_call_id"]
        out.append(msg)
    return out

def count_tokens(tokenizer, messages) -> int:
    if not messages:
        return 0
    hf_messages = flatten_openai_messages(messages)
    try:
        flatten_text = tokenizer.apply_chat_template(
            hf_messages,
            tokenize=False,
            add_generation_prompt=False
        )
        return len(tokenizer.encode(flatten_text))
    except Exception:
        total_chars = sum(len(str(m.get("content", ""))) for m in hf_messages)
        return int(total_chars / 3.0)

async def evaluate_turn(turn, state, agent, tokenizer):
    question = turn.get("question", "")
    
    num_msgs_before = len(state.messages)
    sql_msgs_before = len(state.text2sql_state.messages) if state.text2sql_state else 0
    chart_msgs_before = len(state.text2chart_state.messages) if state.text2chart_state else 0
    
    state.user_request = question
    
    try:
        updated_state = await agent.ainvoke(state)
    except Exception as exc:
        print(f"Error during agent invocation: {exc}")
        updated_state = state

    new_msgs = updated_state.messages[num_msgs_before:]
    
    classification = turn.get("classification", {})
    requires_sql = classification.get("requires_sql", False)
    requires_chart = classification.get("requires_chart", False)
    
    turn_metrics = {
        "turn_index": turn.get("turn_index"),
        "question": question,
        "requires_sql": requires_sql,
        "requires_chart": requires_chart,
        "called_sql": False,
        "called_chart": False,
        "bi_agent_tokens": 0,
        "num_tool_calls": 0,
        "sql_tool_calls_count": 0,
        "chart_tool_calls_count": 0,
        "sql_generated_length": 0,
        "chart_generated_length": 0,
        "sql_tokens": 0,
        "chart_tokens": 0,
        "tool_arguments_length": 0,
    }
    
    turn_metrics["bi_agent_tokens"] = count_tokens(tokenizer, updated_state.messages[1:])
    
    for msg in new_msgs:
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            turn_metrics["num_tool_calls"] += len(tool_calls)
            for tc in tool_calls:
                fn_name = tc.get("function", {}).get("name")
                args_str = tc.get("function", {}).get("arguments", "{}")
                turn_metrics["tool_arguments_length"] += len(args_str)
                
                if fn_name == TEXT2SQL_TOOL_NAME:
                    turn_metrics["called_sql"] = True
                    turn_metrics["sql_tool_calls_count"] += 1
                elif fn_name == TEXT2CHART_TOOL_NAME:
                    turn_metrics["called_chart"] = True
                    turn_metrics["chart_tool_calls_count"] += 1
                    
    # Flags logic: 1 if called correctly according to need, 0 otherwise
    turn_metrics["flag_sql"] = 1 if requires_sql == turn_metrics["called_sql"] else 0
    turn_metrics["flag_chart"] = 1 if requires_chart == turn_metrics["called_chart"] else 0
    
    if updated_state.text2sql_state:
        turn_metrics["sql_tokens"] = count_tokens(tokenizer, updated_state.text2sql_state.messages[1:])
                
    if updated_state.text2chart_state:
        turn_metrics["chart_tokens"] = count_tokens(tokenizer, updated_state.text2chart_state.messages[1:])
                
    # Tính ratio
    turn_metrics["sql_tokens_per_call"] = turn_metrics["sql_tokens"] / turn_metrics["sql_tool_calls_count"] if turn_metrics["sql_tool_calls_count"] > 0 else 0
    turn_metrics["chart_tokens_per_call"] = turn_metrics["chart_tokens"] / turn_metrics["chart_tool_calls_count"] if turn_metrics["chart_tool_calls_count"] > 0 else 0

    return updated_state, turn_metrics


async def run_evaluation(session_data: dict, output_file: str, args: argparse.Namespace, tokenizer, write_lock: asyncio.Lock):
    session_id = session_data.get("id")
    if session_id is None:
        return
        
    print(f"Processing session {session_id}...")
    
    current_time = "2025-12-31"
    text2sql_agent_config = {
        "agent_type": "text2sql",
        "streaming": False,
        "remove_think_tag": False,
        "model_name": args.base_model,
        "urls" : ["http://localhost:9004/sse"]
    }
    text2chart_agent_config = {
        "agent_type": "text2chart",
        "streaming": False,
        "remove_think_tag": False,
        "model_name": args.base_model,
        "urls" : []
    }
    bi_agent_config = {
        "agent_type": "bi_agent",
        "streaming": False,
        "remove_think_tag": False,
        "model_name": args.base_model,
        "text2sql_agent_config": text2sql_agent_config,
        "text2chart_agent_config": text2chart_agent_config,
    }
    text2sql_state_config = {"agent_type": "text2sql", "current_time": current_time}
    text2chart_state_config = {"agent_type": "text2chart", "current_time": current_time}
    bi_agent_state_config = {
        "agent_type": "bi_agent",
        "current_time": current_time,
        "text2sql_state_config": text2sql_state_config,
        "text2chart_state_config": text2chart_state_config
    }
    
    state = get_agent_state(**bi_agent_state_config)
    agent_config = get_agent_config(**bi_agent_config)

    agent = get_agent(config=agent_config)
    await agent.initialize()
    
    session_metrics = {
        "session_id": session_id,
        "total_bi_agent_tokens": 0,
        "total_sql_tokens": 0,
        "total_chart_tokens": 0,
        "total_tool_calls": 0,
        "turns": []
    }
    
    turns = session_data.get("turns", [])
    for turn in turns:
        print(f"  Turn {turn.get('turn_index')}: {turn.get('question')}")
        state, turn_metrics = await evaluate_turn(turn, state, agent, tokenizer)
        session_metrics["turns"].append(turn_metrics)
        session_metrics["total_bi_agent_tokens"] += turn_metrics["bi_agent_tokens"]
        session_metrics["total_sql_tokens"] += turn_metrics["sql_tokens"]
        session_metrics["total_chart_tokens"] += turn_metrics["chart_tokens"]
        session_metrics["total_tool_calls"] += turn_metrics["num_tool_calls"]
        
    async with write_lock:
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(session_metrics, ensure_ascii=False) + '\n')
            
    print(f"Finished session {session_id}")


def load_processed_session_ids(output_file: str) -> list[int]:
    if not os.path.exists(output_file):
        return []
    with open(output_file, 'r', encoding='utf-8') as f:
        sessions = []
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                sid = json.loads(line).get('session_id')
                if sid is not None:
                    sessions.append(sid)
            except json.JSONDecodeError:
                continue
    return sessions


async def run_evaluation_on_dataset(args):
    dataset = fix_and_load_json(args.input_file)
    processed_sessions = load_processed_session_ids(args.output_file)
    
    sessions = [s for s in dataset if s.get('id') not in processed_sessions]
    print(f"Loaded {len(sessions)} sessions for evaluation (skipped {len(processed_sessions)} already processed)")
    
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_model, use_fast=True)
    
    semaphore = asyncio.Semaphore(args.num_worker)
    write_lock = asyncio.Lock()

    async def sem_run(session):
        async with semaphore:
            try:
                await run_evaluation(session, args.output_file, args, tokenizer, write_lock)
            except Exception as e:
                print(f"[SKIP] Session failed: {session.get('id')}")
                print(f"Error: {e}")
                traceback.print_exc()

    await asyncio.gather(*[sem_run(s) for s in sessions])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_file", type=str, required=True)
    parser.add_argument("--output_file", type=str, required=True)
    parser.add_argument("--base_model", type=str, default="openrouter:openai/gpt-oss-120b")
    parser.add_argument("--tokenizer_model", type=str, default="Qwen/Qwen3-4B")
    parser.add_argument("--num_worker", type=int, default=1)
    args = parser.parse_args()
    
    asyncio.run(run_evaluation_on_dataset(args))
