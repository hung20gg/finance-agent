import json
import argparse
import os
import threading
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

from question_generator.generator import PostgresGeneratorConfig
from generator_sql import PostgresLoader

import sys
sys.path.append('..')

from agent.llm import get_llm_wrapper
from dotenv import load_dotenv

import pandas as pd

load_dotenv()

PROMPT = """
<Task>
Bạn được cho một câu hỏi thô và một số thông tin về các thực thể có trong câu hỏi.
Hãy viết lại câu hỏi một cách tự nhiên nhất
</Task>

<Input>
{input}
</Input>

<Addition_info>
{info}
</Addition_info>

<Note>
- Giữ nguyên cụm "điểm phần trăm"
- Hãy viết một cách tự nhiên, đặc biệt là tên ngành
- Chỉ trả lại câu hỏi, không bổ xung gì thêm
- Nếu là câu vẽ biểu đồ thì thêm "Vẽ biểu đồ" vào đầu
</Note>
"""

# =========================
# 🔥 LOAD DB ONCE (IMPORTANT)
# =========================
def load_company_map(postgres_loader):
    df = postgres_loader.query_df("""
        SELECT stock_code, company_name as detail_exp
        FROM company_info
    """)
    return df.set_index('stock_code')['detail_exp'].to_dict()


# =========================
# ⚡ FAST IN-MEMORY LOOKUP
# =========================
def get_description_entities(company_map, entities):
    if not entities:
        return "Không có thông tin thực thể."

    rows = [(e, company_map.get(e, "")) for e in entities]
    df = pd.DataFrame(rows, columns=['stock_code', 'detail_exp'])
    return df.to_markdown(index=False)


# =========================
# 🤖 LLM CALL
# =========================
def smoothen_query(question_raw: str, info: str):
    llm = get_llm_wrapper(model_name="openrouter:openai/gpt-oss-120b")
    prompt = PROMPT.format(input=question_raw, info=info)

    response = llm(messages=[{"role": "user", "content": prompt}])
    return response.split('</think>')[-1]


write_lock = threading.Lock()


# =========================
# 🔄 MAIN PROCESS FUNCTION
# =========================
def process_query(company_map, question, output_file):
    entities = question.get('entities', [])

    try:
        info = get_description_entities(company_map, entities)
    except Exception as e:
        print(f"Error fetching entities: {e}")
        info = "Không có thông tin thực thể."

    try:
        question['question'] = smoothen_query(question.get('question_raw'), info)
    except Exception as e:
        print(f"Error calling LLM for {question.get('id')}: {e}")
        return

    with write_lock:
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(question, ensure_ascii=False) + '\n')


# =========================
# 📂 LOAD UNPROCESSED
# =========================
def get_unprocessed_question(input_file, output_file):
    question_raws = []

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                question_raws.append(json.loads(line))

    processed_ids = set()
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        q = json.loads(line)
                        processed_ids.add(q['id'])
                    except:
                        pass

    print(f"Found {len(processed_ids)} already processed questions.")
    return [q for q in question_raws if q['id'] not in processed_ids]


# =========================
# 🚀 MAIN
# =========================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()

    config = PostgresGeneratorConfig(
        postgres_url=os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    )

    postgres_loader = PostgresLoader(config)

    # 🔥 LOAD ONCE
    print("Loading company data into RAM...")
    company_map = load_company_map(postgres_loader)
    print(f"Loaded {len(company_map)} companies")

    unprocessed = get_unprocessed_question(args.input, args.output)
    print(f"Found {len(unprocessed)} unprocessed questions.")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(process_query, company_map, q, args.output)
            for q in unprocessed
        ]

        for _ in tqdm(as_completed(futures), total=len(futures)):
            pass