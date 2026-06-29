import argparse
import json
import multiprocessing as mp
import os
import re
from typing import List, Tuple

from postgres_eval import execute_query, resolve_db_target


exec_result = []


def replace_multiple_spaces(text):
    return re.sub(r"\s+", " ", text)


def load_json(path):
    with open(path, "r", encoding="utf8") as file:
        return json.loads(file.read())


def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def result_callback(result):
    exec_result.append(result)


def execute_sql(predicted_sql, ground_truth, db_target, timeout_seconds):
    predicted_res = execute_query(predicted_sql, db_target, timeout_seconds=timeout_seconds)
    ground_truth_res = execute_query(ground_truth, db_target, timeout_seconds=timeout_seconds)
    return int(set(predicted_res) == set(ground_truth_res))


def execute_model(predicted_sql, ground_truth, db_target, idx, meta_time_out):
    try:
        res = execute_sql(
            predicted_sql=predicted_sql,
            ground_truth=ground_truth,
            db_target=db_target,
            timeout_seconds=meta_time_out,
        )
    except Exception:
        res = 0
    return {"sql_idx": idx, "res": res}


def package_sqls(sql_path, mode="gpt"):
    clean_sqls = []
    db_ids = []
    if mode == "gpt":
        sql_data = json.load(open(sql_path, "r", encoding="utf8"))
        for _, sql_str in sql_data:
            if isinstance(sql_str, str):
                sql, db_name = sql_str.split("\t----- bird -----\t")
            else:
                sql, db_name = " ", "financial"
            clean_sqls.append(sql)
            db_ids.append(db_name)
    elif mode == "gt":
        for sql_str in open(sql_path, encoding="utf8").readlines():
            sql, db_name = sql_str.strip().split("\t")
            clean_sqls.append(sql)
            db_ids.append(db_name)
    return clean_sqls, db_ids


def run_sqls_parallel(sqls, db_targets, num_cpus=1, meta_time_out=30.0):
    pool = mp.Pool(processes=num_cpus)
    for idx, sql_pair in enumerate(sqls):
        predicted_sql, ground_truth = sql_pair
        pool.apply_async(
            execute_model,
            args=(predicted_sql, ground_truth, db_targets[idx], idx, meta_time_out),
            callback=result_callback,
        )
    pool.close()
    pool.join()


def sort_results(list_of_dicts):
    return sorted(list_of_dicts, key=lambda x: x["sql_idx"])


def compute_acc_by_diff(results, diff_json_path):
    num_queries = len(results)
    contents = load_json(diff_json_path)
    buckets = {"simple": [], "moderate": [], "challenging": []}
    for index, content in enumerate(contents):
        difficulty = content.get("difficulty", "simple")
        buckets.setdefault(difficulty, []).append(results[index])

    simple_acc = sum(item["res"] for item in buckets["simple"]) / len(buckets["simple"])
    moderate_acc = (
        sum(item["res"] for item in buckets["moderate"]) / len(buckets["moderate"])
        if buckets["moderate"]
        else 0
    )
    challenging_acc = (
        sum(item["res"] for item in buckets["challenging"]) / len(buckets["challenging"])
        if buckets["challenging"]
        else 0
    )
    all_acc = sum(item["res"] for item in results) / num_queries
    count_lists = [
        len(buckets["simple"]),
        len(buckets["moderate"]),
        len(buckets["challenging"]),
        num_queries,
    ]
    return simple_acc * 100, moderate_acc * 100, challenging_acc * 100, all_acc * 100, count_lists


def print_data(score_lists, count_lists):
    levels = ["simple", "moderate", "challenging", "total"]
    print("{:20} {:20} {:20} {:20} {:20}".format("", *levels))
    print("{:20} {:<20} {:<20} {:<20} {:<20}".format("count", *count_lists))
    print("======================================    ACCURACY    =====================================")
    print("{:20} {:<20.2f} {:<20.2f} {:<20.2f} {:<20.2f}".format("accuracy", *score_lists))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--predicted_sql_json_path", type=str, required=True)
    parser.add_argument("--ground_truth_sql_path", type=str, required=True)
    parser.add_argument("--data_mode", type=str, required=True, default="dev", choices=["train", "dev", "test"])
    parser.add_argument("--db_root_path", type=str, default="")
    parser.add_argument("--postgres-url", type=str, default=os.getenv("POSTGRES_URL"))
    parser.add_argument("--schema", type=str, default=os.getenv("MAC_SQL_POSTGRES_SCHEMA", "public"))
    parser.add_argument("--db-config-path", type=str, default=os.getenv("MAC_SQL_DB_CONFIG_PATH", ""))
    parser.add_argument("--num_cpus", type=int, default=1)
    parser.add_argument("--meta_time_out", type=float, default=30.0)
    parser.add_argument("--mode_predict", type=str, default="gpt")
    parser.add_argument("--difficulty", type=str, default="simple")
    parser.add_argument("--diff_json_path", type=str, default="./data/bird/dev.json")
    args = parser.parse_args()

    pred_queries, pred_db_ids = package_sqls(args.predicted_sql_json_path, mode=args.mode_predict)
    gt_queries, gt_db_ids = package_sqls(args.ground_truth_sql_path, mode="gt")
    if len(pred_queries) == 0:
        raise ValueError(f"Empty data in {args.predicted_sql_json_path}")
    if len(pred_queries) != len(gt_queries):
        raise AssertionError("len(pred_queries) != len(gt_queries)")
    if pred_db_ids != gt_db_ids:
        raise AssertionError("Predicted SQL db ids do not align with ground-truth db ids")

    db_targets = [
        resolve_db_target(
            db_id=db_id,
            db_root_path=args.db_root_path,
            postgres_url=args.postgres_url,
            schema=args.schema,
            db_config_path=args.db_config_path or None,
        )
        for db_id in pred_db_ids
    ]
    query_pairs = list(zip(pred_queries, gt_queries))
    run_sqls_parallel(query_pairs, db_targets=db_targets, num_cpus=args.num_cpus, meta_time_out=args.meta_time_out)
    exec_result = sort_results(exec_result)

    out_dir = os.path.dirname(args.predicted_sql_json_path)
    os.makedirs(out_dir, exist_ok=True)
    result_json_path = os.path.join(out_dir, f"eval_result_{args.data_mode}.json")

    raw_json_data = load_json(args.diff_json_path)
    pred_sqls = [replace_multiple_spaces(sql) for sql in pred_queries]
    result_json_lst = []
    for idx, item in enumerate(raw_json_data):
        item["pred"] = pred_sqls[idx]
        item["gold"] = replace_multiple_spaces(item.get("SQL", ""))
        if "SQL" in item:
            del item["SQL"]
        item["res"] = exec_result[idx]["res"]
        result_json_lst.append(item)
    save_json_file(result_json_path, result_json_lst)

    simple_acc, moderate_acc, challenging_acc, acc, count_lists = compute_acc_by_diff(
        exec_result,
        args.diff_json_path,
    )
    print_data([simple_acc, moderate_acc, challenging_acc, acc], count_lists)
    print("===========================================================================================")
    print("Finished evaluation")
