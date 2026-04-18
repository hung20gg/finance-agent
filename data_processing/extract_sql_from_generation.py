import json
import os

def main():
    results_path = "../data/eval_test_hint_results_openrouter_qwen_qwen3.5-122b-a10b.jsonl"
    clean_path = "data_mix_v5/test.clean.jsonl"
    final_path = "data_mix_v5/test.final.jsonl"

    print(f"Reading Ground Truth from: {clean_path}")
    # Đọc dữ liệu GT
    clean_data = {}
    if os.path.exists(clean_path):
        with open(clean_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                obj = json.loads(line)
                clean_data[obj["id"]] = obj
    else:
        print(f"Lỗi: Không tìm thấy {clean_path}")
        return

    print(f"Extracting SQL from: {results_path}")
    extracted_count = 0
    total_count = 0

    # Đọc eval results, trích xuất SQL và ghi ra file mới
    with open(results_path, 'r', encoding='utf-8') as f_in, \
         open(final_path, 'w', encoding='utf-8') as f_out:
        
        for line in f_in:
            if not line.strip(): continue
            total_count += 1
            res = json.loads(line)
            record_id = res.get("id")
            messages = res.get("messages", [])
            
            sql_query = None
            
            # Lặp ngược messages từ dưới lên để lấy lệnh execute_code cuối cùng
            for msg in reversed(messages):
                if msg.get("role") == "assistant" and "tool_calls" in msg:
                    for tc in msg["tool_calls"]:
                        func = tc.get("function", {})
                        if func.get("name") == "execute_code":
                            args_str = func.get("arguments", "{}")
                            try:
                                args = json.loads(args_str)
                                if "query" in args:
                                    sql_query = args["query"]
                                    # Thoát loop tool_calls
                                    break
                            except json.JSONDecodeError:
                                pass
                    if sql_query:
                        # Thoát loop messages nếu đã tìm thấy execute_code cuối cùng
                        break
            
            # Khớp với dữ liệu test.clean.jsonl
            if record_id in clean_data:
                gt_obj = clean_data[record_id].copy()
                gt_obj["SQL"] = sql_query  # Trích xuất SQL lưu vào key 'SQL'
                
                # Lưu ra file test.final.jsonl
                f_out.write(json.dumps(gt_obj, ensure_ascii=False) + "\n")
                
                if sql_query:
                    extracted_count += 1
            else:
                print(f"Warning: ID {record_id} không có trong test.clean.jsonl")
                
    print(f"Đã xử lý {total_count} dòng.")
    print(f"Đã trích xuất thành công SQL cho {extracted_count} record(s).")
    print(f"File output đã được lưu tại: {final_path}")

if __name__ == "__main__":
    main()
