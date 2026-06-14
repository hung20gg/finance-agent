import os
import re
import glob
from client import PostgresClient
from logger import logger
from rapidfuzz import fuzz


examples = []


def load_examples(example_dir=None):
    """Load example SQL pairs from all example*.md files in the given directory.
    
    Supports multiple example files — any file matching the pattern
    ``example*.md`` in the directory will be parsed.
    
    Args:
        example_dir: Directory containing example markdown files.
                     Defaults to the directory of this module.
    """
    if examples:
        return

    if example_dir is None:
        example_dir = os.path.dirname(__file__)

    # Support env-override for example directory
    example_dir = os.environ.get("EXAMPLE_SQL_DIR", example_dir)

    pattern = os.path.join(example_dir, "example*.md")
    matched_files = sorted(glob.glob(pattern))

    if not matched_files:
        logger.warning(f"No example files found matching '{pattern}'")
        return

    for filepath in matched_files:
        _parse_example_file(filepath)

    logger.info(f"Loaded {len(examples)} example SQL pairs from {len(matched_files)} file(s)")


def _parse_example_file(filepath: str):
    """Parse a single example markdown file and append entries to the global list."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Failed to read example file '{filepath}': {e}")
        return

    blocks = content.split("## ")
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.split("\n", 1)
        if len(lines) < 2:
            continue

        question = lines[0].strip()
        body = lines[1].strip()

        sql_match = re.search(r'```sql\n(.*?)\n```', body, re.DOTALL)
        if sql_match:
            sql = sql_match.group(1).strip()
            examples.append({"question": question, "sql": sql})


def fuzzy_search_examples(query: str, n: int = 5, threshold: int = 50):
    """Find the top-N example SQL pairs most similar to the query.
    
    Args:
        query: User's natural language question.
        n: Maximum number of results to return.
        threshold: Minimum WRatio score to include a candidate.
    
    Returns:
        List of matching example dicts with 'question' and 'sql' keys.
    """
    candidates = []

    for ex in examples:
        score = fuzz.WRatio(query.lower(), ex["question"].lower())
        if score > threshold:
            candidates.append((score, ex))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [ex for _, ex in candidates[:n]]


def register_tool(mcp, client: PostgresClient):
    load_examples()

    @mcp.tool()
    async def get_example_sql(query: str) -> str:
        """
        Get similar example SQL queries based on the user's question using fuzzy search. You should use this to get the sample
        for your SQL generation

        Args:
            query: The user's question, used to find similar examples.
        Returns:
            The top 5 most similar example SQL queries as a string.
        """
        if not examples:
            return "No examples available."

        top_examples = fuzzy_search_examples(query, n=5)

        if not top_examples:
            return "No similar examples found."

        res = "Top similar examples:\n\n"
        for i, ex in enumerate(top_examples, 1):
            res += f"{i}. Question: {ex['question']}\nSQL:\n```sql\n{ex['sql']}\n```\n\n"
        return res
