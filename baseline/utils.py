import re
from typing import Any, Dict, List, Optional


def extract_tool_text(tool_result: Any) -> str:
    content = getattr(tool_result, "content", None)
    if isinstance(content, list) and content:
        first_item = content[0]
        text = getattr(first_item, "text", None)
        if text is not None:
            return text

        if isinstance(first_item, dict):
            text = first_item.get("text")
            if text is not None:
                return text

    return str(tool_result)


def extract_entity_answer(sql_result: str) -> Optional[str]:
    if not sql_result or "[FAILED]" in sql_result:
        return "NO_DATA"

    table_lines = [
        line.strip()
        for line in sql_result.splitlines()
        if line.strip().startswith("|") and line.strip().endswith("|")
    ]
    if len(table_lines) < 3:
        return None

    data_lines = []
    for line in table_lines[2:]:
        normalized = line.replace("|", "").replace(":", "").replace("-", "").strip()
        if normalized:
            data_lines.append(line)
    if not data_lines:
        return "NO_DATA"

    cells = [cell.strip() for cell in data_lines[0].strip("|").split("|")]
    value = next((cell for cell in reversed(cells) if cell), "")
    return value or "NO_DATA"



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
