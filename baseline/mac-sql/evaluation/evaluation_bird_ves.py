import argparse
import json
import math
import multiprocessing as mp
import os
import sys
from typing import List

import numpy as np

from postgres_eval import execute_query, resolve_db_target, time_query


exec_result = []


def result_callback(result):
    exec_result.append(result)


def clean_abnormal(values: List[float]) -> List[float]:
    values = np.asarray(values)
    processed_list = []
    mean = np.mean(values, axis=0)
    std = np.std(values, axis=0)
    for value in values:
        if mean - 3 * std < value < mean + 3 * std:
            processed_list.append(value)
    return processed_list


def iterated_execute_sql(predicted_sql, ground_truth, db_target, iterate_num, timeout_seconds):
    predicted_res = execute_query(predicted_sql, db_target, timeout_seconds=timeout_seconds)
    ground_truth_res = execute_query(ground_truth, db_target, timeout_seconds=timeout_seconds)
    time_ratio = 0.0
    if set(predicted_res) == set(ground_truth_res):
        diff_list = []
        for _ in range(iterate_num):
            predicted_time = time_query(predicted_sql, db_target, timeout_seconds=timeout_seconds)
            ground_truth_time = time_query(ground_truth, db_target, timeout_seconds=timeout_seconds)
            if predicted_time > 0:
                diff_list.append(ground_truth_time / predicted_time)
        if diff_list:
            processed = clean_abnormal(diff_list)
            time_ratio = sum(processed) / len(processed) if processed else 0.0
    return time_ratio


def execute_model(predicted_sql, ground_truth, db_target, idx, iterate_num, meta_time_out):
    try:
        if idx % 500 == 0:
            print(idx, file=sys.stdout, flush=True)
        time_ratio = iterated_execute_sql(
            predicted_sql=predicted_sql,
            ground_truth=ground_truth,
            db_target=db_target,
            iterate_num=iterate_num,
            timeout_seconds=meta_time_out,
        )
    except Exception:
        time_ratio = 0.0
    return {"sql_idx": idx, "time_ratio": time_ratio}


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


def run_sqls_parallel(sqls, db_targets, num_cpus=1, iterate_num=100, meta_time_out=30.0):
    pool = mp.Pool(processes=num_cpus)
    for idx, sql_pair in enumerate(sqls):
        predicted_sql, ground_truth = sql_pair
        pool.apply_async(
            execute_model,
            args=(predicted_sql, ground_truth, db_targets[idx], idx, iterate_num, meta_time_out),
            callback=result_callback,
        )
    pool.close()
    pool.join()


def sort_results(list_of_dicts):
    return sorted(list_of_dicts, key=lambda x: x["sql_idx"])


def compute_ves(results):
    num_queries = len(results)
    if num_queries == 0:
        return 0
    total_ratio = 0.0
    for result in results:
        total_ratio += math.sqrt(result["time_ratio"]) * 100 if result["time_ratio"] != 0 else 0
    return total_ratio / num_queries


def load_json(path):
    with open(path, "r", encoding="utf8") as file:
        return json.loads(file.read())


def compute_ves_by_diff(results, diff_json_path):
    contents = load_json(diff_json_path)
    buckets = {"simple": [], "moderate": [], "challenging": []}
    for index, content in enumerate(contents):
        buckets.setdefault(content["difficulty"], []).append(results[index])
    counts = [len(buckets["simple"]), len(buckets["moderate"]), len(buckets["challenging"]), len(results)]
    return (
        compute_ves(buckets["simple"]),
        compute_ves(buckets["moderate"]),
        compute_ves(buckets["challenging"]),
        compute_ves(results),
        counts,
    )


def print_data(score_lists, count_lists):
    levels = ["simple", "moderate", "challenging", "total"]
    print("{:20} {:20} {:20} {:20} {:20}".format("", *levels))
    print("{:20} {:<20} {:<20} {:<20} {:<20}".format("count", *count_lists))
    print("=========================================    VES   ========================================")
    print("{:20} {:<20.2f} {:<20.2f} {:<20.2f} {:<20.2f}".format("ves", *score_lists))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--predicted_sql_json_path", type=str, required=True)
    parser.add_argument("--ground_truth_sql_path", type=str, required=True)
    parser.add_argument("--data_mode", type=str, required=True, default="dev")
    parser.add_argument("--db_root_path", type=str, default="")
    parser.add_argument("--postgres-url", type=str, default=os.getenv("POSTGRES_URL"))
    parser.add_argument("--schema", type=str, default=os.getenv("MAC_SQL_POSTGRES_SCHEMA", "public"))
    parser.add_argument("--db-config-path", type=str, default=os.getenv("MAC_SQL_DB_CONFIG_PATH", ""))
    parser.add_argument("--num_cpus", type=int, default=1)
    parser.add_argument("--meta_time_out", type=float, default=30.0)
    parser.add_argument("--mode_gt", type=str, default="gt")
    parser.add_argument("--mode_predict", type=str, default="gpt")
    parser.add_argument("--diff_json_path", type=str, required=True, default="")
    parser.add_argument("--iterate_num", type=int, default=100)
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
    run_sqls_parallel(
        query_pairs,
        iterate_num=args.iterate_num,
        db_targets=db_targets,
        num_cpus=args.num_cpus,
        meta_time_out=args.meta_time_out,
    )
    exec_result = sort_results(exec_result)
    simple_ves, moderate_ves, challenging_ves, ves, count_lists = compute_ves_by_diff(
        exec_result,
        args.diff_json_path,
    )
    print_data([simple_ves, moderate_ves, challenging_ves, ves], count_lists)
    print("===========================================================================================")
    print("Finished evaluation")
