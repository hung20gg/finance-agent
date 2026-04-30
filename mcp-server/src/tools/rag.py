import os
import re
from client import PostgresClient
from rapidfuzz import fuzz


examples = []

def load_examples():
    if examples:
        return
    example_path = os.path.join(os.path.dirname(__file__), "example.md")
    if not os.path.exists(example_path):
        return
    with open(example_path, "r", encoding="utf-8") as f:
        content = f.read()

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
