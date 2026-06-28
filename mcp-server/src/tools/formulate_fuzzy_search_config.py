import json
import re
from client import PostgresClient
from agent.llm import get_llm_wrapper

llm = get_llm_wrapper("groq:openai/gpt-oss-120b")

_formulate_prompt = """
# ROLE
You are a professional data analyst. You can smartly read and analyze SQL Tables schemas.

# TASK
You are going to be given a list of table schemas. Each table schema has an attached data record for example. Your task is to analyze the table schema and data records and come up with a fuzzy search configuration for each table.

# OUTPUT FORMAT
Must ONLY return a valid JSON Object with following structure:

{{
    "search_backend": "rapidfuzz",
    "searchable_entities": {{
        "<entity_key>": {{
            "table_name": "<table name>",
            "search_columns": ["<column 1>", "<column 2>", ...],
            "return_columns": ["<column 1>", "<column 2>", ...],
            "description": "<description>",
            "threshold": <threshold>,
            "limit": <limit>,
            "distinct": <distinct>
        }}
    }}
}}

# CONSTRAINTS
- `<entity_key>` must be a short, clean, descriptive string representing the search entity type (e.g. 'company', 'financial_ratio', 'market_index')
- `search_columns` and `return_columns` must be exactly the column names in the table schema
- `description` must be in English and explain what information the entity contains
- `distinct` must be true if the table contains duplicate values, false otherwise
- `threshold` is a value between 0 and 100 used to determine the similarity between the query and the values in the table
- `limit` is the maximum number of results to return

# NOTE
- The generated fuzzy search config MUST be smart and reasonable based on the table schema and data records
- DO NOT return any redundant text in the response except for the JSON Object

# INPUTS
{schema_table_list}
"""

def get_all_table_schemas(client: PostgresClient):
    sql = """
        SELECT 
            table_name,
            jsonb_agg(jsonb_build_object(
                'column_name', column_name,
                'data_type', data_type
            )) AS columns
        FROM information_schema.columns
        WHERE table_schema = 'public'
        GROUP BY table_name
    """

    result = client.execute_query(sql)
    return [dict(row) for row in result]

def _parse_llm_json(response: str) -> dict:
    """Robustly parse JSON object from LLM response string."""
    # Remove think tags if present
    if "<think>" in response and "</think>" in response:
        response = response.split("</think>", 1)[1]
    
    # Strip markdown block fences if present
    match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL | re.IGNORECASE)
    if match:
        json_str = match.group(1)
    else:
        match = re.search(r"```\s*(.*?)\s*```", response, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            json_str = response
            
    json_str = json_str.strip()
    return json.loads(json_str)

def get_first_record(client: PostgresClient, table_name: str) -> dict | None:
    """Fetch the first record of the given table as a dictionary."""
    sql = f"SELECT * FROM {table_name} LIMIT 1"
    try:
        results = client.execute_query(sql)
        if results:
            return dict(results[0])
    except Exception:
        return None
    return None

def _make_json_safe(record: dict) -> dict | None:
    """Convert dict values to JSON-serializable types."""
    if record is None:
        return None
    safe_record = {}
    for k, v in record.items():
        if v is None or isinstance(v, (str, int, float, bool)):
            safe_record[k] = v
        else:
            safe_record[k] = str(v)
    return safe_record

def formulate_fuzzy_search_config(client: PostgresClient) -> dict:
    table_schemas = get_all_table_schemas(client=client)

    schema_table_list = []
    for table in table_schemas:
        table_name = table["table_name"]
        raw_record = get_first_record(client, table_name)
        record_example = _make_json_safe(raw_record)
        schema_table_list.append({
            "table_name": table_name,
            "columns": table["columns"],
            "record_example": record_example
        })

    prompt = _formulate_prompt.format(schema_table_list=json.dumps(schema_table_list, indent=2))
    messages = [
        {"role": "user", "content": prompt}
    ]
    response = llm.invoke(messages)
    return _parse_llm_json(response)