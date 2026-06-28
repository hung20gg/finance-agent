import json
import os
import random
import re
import time
from typing import Dict, List, Optional


def is_valid_date(date_str):
    if not isinstance(date_str, str):
        return False
    date_str = date_str.split()[0]
    if len(date_str) != 10:
        return False
    pattern = r"^\d{4}-\d{2}-\d{2}$"
    if re.match(pattern, date_str):
        year, month, day = map(int, date_str.split("-"))
        return year >= 1 and 1 <= month <= 12 and 1 <= day <= 31
    return False


def is_valid_date_column(col_value_lst):
    for col_value in col_value_lst:
        if not is_valid_date(col_value):
            return False
    return True


def is_email(string):
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, string) is not None


def extract_world_info(message_dict: dict):
    return {
        "idx": message_dict.get("idx", 0),
        "db_id": message_dict.get("db_id", ""),
        "query": message_dict.get("query", ""),
        "evidence": message_dict.get("evidence", ""),
        "difficulty": message_dict.get("difficulty", ""),
        "ground_truth": message_dict.get("ground_truth", ""),
        "send_to": message_dict.get("send_to", ""),
    }


def replace_multiple_spaces(text):
    return re.sub(r"\s+", " ", text)


def extract_table_names(sql_query):
    sql_query = sql_query.replace("`", "").replace('"', "")
    table_names = re.findall(r"FROM\s+([\w\.]+)", sql_query, re.IGNORECASE) + re.findall(
        r"JOIN\s+([\w\.]+)", sql_query, re.IGNORECASE
    )
    return set(table_names)


def check_selector_response(json_data: Dict) -> bool:
    flags = ["keep_all", "drop_all"]
    for _, value in json_data.items():
        if isinstance(value, str):
            if value not in flags:
                return False
        elif not isinstance(value, list):
            return False
    return True


def load_json_file(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_jsonl_file(path):
    with open(path, "r", encoding="utf-8") as file:
        data = []
        for line in file:
            line = line.strip()
            if line:
                data.append(json.loads(line))
        return data


def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def save_jsonl_file(path, data):
    with open(path, "w", encoding="utf-8") as file:
        for item in data:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")


def save_file(path, string_lst):
    with open(path, "w", encoding="utf-8") as file:
        file.writelines(string_lst)


def parse_json(text: str) -> dict:
    start = text.find("```json")
    end = text.find("```", start + 7)
    if start == -1 or end == -1:
        return {}
    json_string = text[start + 7 : end]
    try:
        json_data = json.loads(json_string)
    except Exception:
        return {}
    return json_data if check_selector_response(json_data) else {}


def parse_sql_from_string(input_string: str):
    sql_pattern = r"```(?:sql|postgresql|psql)?\s*(.*?)```"
    all_sqls = []
    for match in re.finditer(sql_pattern, input_string, re.DOTALL | re.IGNORECASE):
        all_sqls.append(match.group(1).strip())
    if all_sqls:
        return all_sqls[-1]
    return parse_sql(input_string)


def parse_sql(res: str) -> str:
    if "SELECT" not in res and "select" not in res:
        return res.strip()
    res = res.replace("\n", " ")
    return res.strip()


def add_prefix(sql):
    stripped = sql.lstrip()
    if stripped.upper().startswith("SELECT") or stripped.upper().startswith("WITH"):
        return stripped
    return "SELECT " + stripped


def parse_qa_pairs(res: str, end_pos=2333) -> list:
    from core.const import subq_pattern

    lines = res.split("\n")
    qa_pairs = []
    end_pos = len(lines) if end_pos == 2333 else end_pos
    for idx in range(0, end_pos):
        if re.findall(subq_pattern, lines[idx], re.IGNORECASE) != []:
            query = lines[idx]
            start_idx = -1
            end_idx = -1
            for idx2 in range(idx + 1, end_pos):
                if "```" in lines[idx2]:
                    start_idx = idx2
                    break
            if start_idx == -1:
                return []
            for idx3 in range(start_idx + 1, end_pos):
                if "```" in lines[idx3]:
                    end_idx = idx3
                    break
            if end_idx == -1:
                return []
            answer = " ".join(lines[start_idx + 1 : end_idx])
            qa_pairs.append((str(query), str(answer)))
    return qa_pairs


def get_files(root, suffix):
    import glob

    if not os.path.exists(root):
        raise FileNotFoundError(f"path {root} not found.")
    return [os.path.abspath(path) for path in glob.glob(f"{root}/**/*{suffix}", recursive=True)]


def rename_file(file_path, new_name):
    dir_name = os.path.dirname(file_path)
    _, file_ext = os.path.splitext(os.path.basename(file_path))
    timestamp = str(int(time.time()))
    new_file_name = new_name + "_" + timestamp + file_ext
    new_file_path = os.path.join(dir_name, new_file_name)
    os.rename(file_path, new_file_path)
    return new_file_path


def sample_without_replacement(values: List[str], k: int) -> List[str]:
    if len(values) <= k:
        return values
    return random.sample(values, k=k)
