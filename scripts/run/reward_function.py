import re
import math
import json
from collections import Counter
from typing import Dict, Any, Optional

# Extract <answer> ... </answer> from the response


# Extract <tool_call> ... </tool_call> from the response
def extract_tool_call(response: str) -> list[str]:     
    matches = re.findall(r"<tool_call>(.*?)</tool_call>", response, re.DOTALL)
    return [m.strip() for m in matches]
    


def chi2_pdf(x, df=15):
    if x < 0:
        return 0.0
    
    coef = 1.0 / ( (2 ** (df / 2.0)) * math.gamma(df / 2.0) )
    return coef * (x ** (df / 2.0 - 1.0)) * math.exp(-x / 2.0)


def extract_boxed_answer(text):
    matches = re.findall(r'\\boxed\{([^}]*)\}', text)
    
    if not matches:
        return None
    
    content = matches[-1].strip()  # take the last box
    
    # Try to convert to float
    try:
        num = float(content)
        return round(num, 2)
    except:
        return content

def extract_answer_from_sql_response(text: str) -> Optional[Dict[str, Any]]:
    """
    Extracts:
    - \\boxed{value} → returns value
    - JSON block (with or without ```json) → returns dict
    """

    # 1. Try to extract \boxed{} — use last match to skip any \boxed{} inside <think> blocks
    boxed_matches = re.findall(r'\\boxed\{([^}]*)\}', text)
    if boxed_matches:
        value = boxed_matches[-1].strip()

        # Try to parse number if possible
        try:
            num = float(value)
            return {
                "value": round(num, 2),
                "type": "number"
            }
        except:
            return {
                "value": value,
                "type": "text"
                }

    # 2. Try to extract ```json block
    json_block_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_block_match:
        try:
            return {
                "value": json.loads(json_block_match.group(1)),
                "type": "json"
            }
        except json.JSONDecodeError:
            pass

    # 3. Try to extract ANY JSON-like object
    json_match = re.search(r'(\{.*\})', text, re.DOTALL)
    if json_match:
        try:
            return {
                "value": json.loads(json_match.group(1)),
                "type": "json"
            }
        except json.JSONDecodeError:
            pass

    return None


_COL_ALIASES = {
    "value": "data", "amount": "data", "val": "data",
    "ticker": "stock_code", "symbol": "stock_code", "code": "stock_code",
    "period": "period_key", "quarter_key": "period_key", "time_key": "period_key",
    "commodity": "indicator_name", "commodity_name": "indicator_name", "item": "indicator_name",
    "market_index": "index_name", "index": "index_name",
}


def compare_json_dicts(pred: dict, gt: dict) -> bool:
    """
    Compare two dict-of-lists tables ignoring row order.
    Handles single-row dicts and normalizes common column name aliases.
    """
    def _norm(d):
        return {_COL_ALIASES.get(k, k): ([v] if not isinstance(v, list) else v)
                for k, v in d.items()}

    pred, gt = _norm(pred), _norm(gt)

    if set(pred.keys()) != set(gt.keys()):
        return False

    keys = sorted(pred.keys())

    # All columns must be list-like and have the same row count.
    if any(not isinstance(pred[k], list) or not isinstance(gt[k], list) for k in keys):
        return False

    pred_lengths = {len(pred[k]) for k in keys}
    gt_lengths = {len(gt[k]) for k in keys}
    if len(pred_lengths) != 1 or len(gt_lengths) != 1:
        return False

    pred_count = pred_lengths.pop()
    gt_count = gt_lengths.pop()
    if pred_count != gt_count:
        return False

    def rows(table: dict) -> list[tuple[Any, ...]]:
        return [
            tuple(table[key][row_index] for key in keys)
            for row_index in range(pred_count)
        ]

    pred_rows = rows(pred)
    gt_rows = rows(gt)

    def round_sig(x, sig=5):
        if x == 0:
            return 0
        return round(x, sig - int(math.floor(math.log10(abs(x)))) - 1)

    def is_close(pr: Any, gt: Any) -> float:
        if isinstance(gt, (int, float)) and isinstance(pr, (int, float)) and type(gt) is not bool and type(pr) is not bool:
            try:
                ground_truth = float(gt)
                pred_val = float(pr)
                eps = 0.01
                if abs(ground_truth) > 10:
                    eps = 0.001 * abs(ground_truth)
                
                gt_rounded = round_sig(ground_truth, 4)
                pr_rounded = round_sig(pred_val, 4)
                if abs(gt_rounded - pr_rounded) <= eps:
                    return 1.0
                elif abs(gt_rounded - pr_rounded * 100) <= eps:
                    return 0.5
                return 0.0
            except Exception:
                return 1.0 if pr == gt else 0.0
        return 1.0 if pr == gt else 0.0

    def rows_match(r1, r2):
        row_score = 0.0
        for v1, v2 in zip(r1, r2):
            s = is_close(v1, v2)
            if s == 0.0:
                return 0.0
            row_score += s
        return row_score / len(r1) if r1 else 1.0

    used_pred = set()
    total_score = 0.0
    for gr in gt_rows:
        best_score = 0.0
        best_idx = -1
        for i, pr in enumerate(pred_rows):
            if i not in used_pred:
                match_score = rows_match(pr, gr)
                if match_score > best_score:
                    best_score = match_score
                    best_idx = i
                    if best_score == 1.0:
                        break
        if best_idx != -1 and best_score > 0:
            used_pred.add(best_idx)
            total_score += best_score
        else:
            return 0.0

    return total_score / len(gt_rows) if gt_rows else 1.0


def _score_prediction(pred: Dict[str, Any], ground_truth: Any) -> float:
    def round_sig(x, sig=5):
        if x == 0:
            return 0
        return round(x, sig - int(math.floor(math.log10(abs(x)))) - 1)

    def coerce_number(value: Any) -> Optional[float]:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            normalized = value.strip().replace(",", "")
            if normalized.endswith("%"):
                normalized = normalized[:-1].strip()
            try:
                return float(normalized)
            except ValueError:
                return None
        return None

    def score_number(pred_value: Any, gt_value: Any) -> float:
        ground_truth_number = coerce_number(gt_value)
        pred_number = coerce_number(pred_value)
        if ground_truth_number is None or pred_number is None:
            return 0.0

        eps = 0.01
        if abs(ground_truth_number) > 10:
            eps = 0.001 * abs(ground_truth_number)

        gt = round_sig(ground_truth_number, 4)
        pr = round_sig(pred_number, 4)
        if abs(gt - pr) <= eps:
            return 1.0
        if abs(gt - pr * 100) <= eps:
            return 0.5
        return 0.0

    if ground_truth is None:
        return 1.0

    if isinstance(ground_truth, (int, float)) and not isinstance(ground_truth, bool):
        return score_number(pred["value"], ground_truth)

    if isinstance(ground_truth, str):
        if coerce_number(ground_truth) is not None:
            return score_number(pred["value"], ground_truth)
        return 1.0 if pred["value"] == ground_truth else 0.0

    if isinstance(ground_truth, dict):
        if not isinstance(pred["value"], dict):
            return 0.0
        return compare_json_dicts(pred["value"], ground_truth)

    return 0.0


def compute_score(solution_str, ground_truth):

    tool_calls = extract_tool_call(solution_str)

    answer = solution_str.split("</tool_call>")[-1].split("</think>")[-1] # crude way to get the answer part after the last tool call
    pred = extract_answer_from_sql_response(answer)

    
    if len(tool_calls) == 0:
        return {
            "num_tool_calls": len(tool_calls),
            "total_score": 0,
            "error": "No tools called",
            "ground_truth": ground_truth,
            "pred": pred
        }
    
    if pred is None:
        return {
            "num_tool_calls": len(tool_calls),
            "total_score": -1,
            "error": "Could not extract answer from response",
            "ground_truth": ground_truth,
            "pred": pred
        }
    score = float(_score_prediction(pred, ground_truth))


    print(f"### Extracted answer: {pred['value']}, ground truth: {ground_truth}, score: {score}")
    
    return {
        "num_tool_calls": len(tool_calls),
        "total_score": score,
        "ground_truth": ground_truth,
        "pred": pred
    }


def compute_score_simple(solution_str, ground_truth):
    """
    Score the final extracted answer only.
    Ignores tool-call presence and any intermediate reasoning.
    """
    answer = solution_str.split("</tool_call>")[-1].split("</think>")[-1]
    pred = extract_answer_from_sql_response(answer)

    if pred is None:
        return {
            "total_score": -1,
            "error": "Could not extract answer from response",
            "ground_truth": ground_truth,
            "pred": pred,
        }

    score = float(_score_prediction(pred, ground_truth))

    print(f"### Simple score extracted answer: {pred['value']}, ground truth: {ground_truth}, score: {score}")

    return {
        "total_score": score,
        "ground_truth": ground_truth,
        "pred": pred,
    }
