import argparse
import json
import os
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent.parent
if str(CURRENT_DIR) in sys.path:
    sys.path.remove(str(CURRENT_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.core.env_config import get_env, load_env_config

load_env_config()

from baseline.mac_sql.core.chat_manager import ChatManager
from baseline.mac_sql.core.const import SYSTEM_NAME


def build_message(question: str, evidence: str, db_id: str) -> dict:
    return {
        "idx": 0,
        "db_id": db_id,
        "query": question,
        "evidence": evidence,
        "extracted_schema": {},
        "ground_truth": "",
        "difficulty": "",
        "send_to": SYSTEM_NAME,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Run the PostgreSQL-adapted MAC-SQL baseline.")
    parser.add_argument("--question", type=str, required=True, help="Natural-language question.")
    parser.add_argument("--evidence", type=str, default="", help="Optional extra evidence or hints.")
    parser.add_argument("--db-id", type=str, default="finance", help="Logical database id used in prompts.")
    parser.add_argument(
        "--postgres-url",
        type=str,
        default=get_env("POSTGRES_URL"),
        help="PostgreSQL connection URL. Defaults to POSTGRES_URL.",
    )
    parser.add_argument("--schema", type=str, default="public", help="PostgreSQL schema name.")
    parser.add_argument(
        "--model",
        type=str,
        default=os.getenv("MAC_SQL_MODEL") or os.getenv("MODEL_NAME") or "openrouter:openai/gpt-oss-120b",
        help="LLM model name routed through agent.llm.",
    )
    parser.add_argument("--log-file", type=str, default="", help="Optional log file path.")
    parser.add_argument(
        "--include-tables",
        nargs="*",
        default=None,
        help="Optional allowlist of tables to expose to the baseline.",
    )
    parser.add_argument(
        "--exclude-tables",
        nargs="*",
        default=None,
        help="Optional denylist of tables to hide from the baseline.",
    )
    parser.add_argument(
        "--without-selector",
        action="store_true",
        default=False,
        help="Skip schema pruning and expose the full selected schema.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.postgres_url:
        raise ValueError("POSTGRES_URL is not set. Pass --postgres-url or define it in the environment.")

    manager = ChatManager(
        postgres_url=args.postgres_url,
        schema=args.schema,
        log_path=args.log_file,
        model_name=args.model,
        include_tables=args.include_tables,
        exclude_tables=args.exclude_tables,
        without_selector=args.without_selector,
    )
    message = build_message(args.question, args.evidence, args.db_id)
    manager.start(message)
    print(json.dumps(message, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
