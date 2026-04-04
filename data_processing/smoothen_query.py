# Convert hard-coded query to natural language query
# Example input: {"question_raw": "Trong quý 3 năm 2025, NIM của mã chứng khoán DSE chênh mức trung bình của ngành Dịch vụ Tài chính bao nhiêu?", "answer_type": "entity", "answer": -0.0085, "question_family": "compare", "question_subtype": "ambiguous::company_vs_industry_avg_diff_NIM", "ambiguity": "ambiguous", "time_asked": "2025-11-11", "gap": 2, "data_cutoff": "2025-11-11", "entities": ["DSE", "Financial Services"], "metrics": ["NIM"], "periods": ["2025-Q3"], "sources": ["company_quarter", "industry_avg_quarter"], "reasoning_hops": 2, "extra_info": {"company_value": 0.0063, "industry_mean": 0.0148, "industry": "Financial Services", "resolved_from_clear_question": "Trong quý 3 năm 2025, NIM của công ty chứng khoán DSE chênh trung bình ngành Dịch vụ Tài chính bao nhiêu?", "ambiguity_rule": "controlled_ambiguity"}, "id": "test-00000015"}

import json
import argparse
import os
from tqdm import tqdm

from question_generator.generator import PostgresGeneratorConfig, QuestionRecord, QuestionGenerator
from generator_sql import PostgresLoader


import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append('..')

from agent.llm import get_llm_wrapper
from dotenv import load_dotenv
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
- Hãy viết một cách tự nhiên, đặc biệt là tên ngành. Đừng cố theo rule sẵn, có thể dùng các từ thông dụng, đơn giản
- Chỉ trả lại câu hỏi, không bổ xung gì thêm
- Chỉ có 2 loại câu hỏi chính: lấy dữ liệu và vẽ biểu đồ. với câu vẽ biểu đồ thì hãy thêm chữ "Vẽ biểu đồ" vào đầu câu hỏi và chọn loại biểu đồ phù hợp.
</Note>
"""


def get_description_entities(postgres_loader: PostgresLoader, entities: list[str]):

    query = """
    SELECT stock_code, company_name as detail_exp
    FROM company_info
    WHERE stock_code IN ({}) 
    """.format(",".join([f"'{e}'" for e in entities]))


    df = postgres_loader.query_df(query)

    return df.to_markdown()

def smoothen_query(question_raw: str, info: str):
    llm = get_llm_wrapper(model_name="openrouter:openai/gpt-oss-120b")
    prompt = PROMPT.format(input=question_raw, info=info)
    
    response = llm(messages=[{"role": "user", "content": prompt}])
    return response.split('</think>')[-1]

write_lock = threading.Lock()

def process_query(postgres_loader, question, output_file):
    entities = question.get('entities', [])
    if entities:
        try:
            info = get_description_entities(postgres_loader, entities)
        except Exception as e:
            print(f"Error fetching entities: {e}")
            info = "Không có thông tin thực thể."
    else:
        info = "Không có thông tin thực thể."
        
    try:
        question['question'] = smoothen_query(question.get('question_raw'), info)
    except Exception as e:
        print(f"Error calling llm for question {question.get('id')}: {e}")
        return
    
    with write_lock:
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(question, ensure_ascii=False) + '\n')
    

def get_unprocessed_question(input_file, output_file):
    import os

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
                    except json.JSONDecodeError:
                        pass

    selected_questions = []
    for q in question_raws:
        if q['id'] not in processed_ids:
            selected_questions.append(q)

    return selected_questions


if __name__ == "__main__":
    

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True, help="Input JSONL file")
    parser.add_argument("--output", type=str, required=True, help="Output JSONL file")
    parser.add_argument("--workers", type=int, default=5, help="Number of worker threads")
    args = parser.parse_args()

    config = PostgresGeneratorConfig(postgres_url=os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL"))
    postgres_loader = PostgresLoader(config)

    unprocessed = get_unprocessed_question(args.input, args.output)
    print(f"Found {len(unprocessed)} unprocessed questions.")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_query, postgres_loader, q, args.output): q for q in unprocessed}
        for future in tqdm(as_completed(futures), total=len(futures)):
            pass