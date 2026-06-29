import itertools
import re
from typing import Iterator, List, Set, Tuple


VALUE_NUM_SYMBOL = "valuerare"


def postprocess(query: str) -> str:
    return query.replace("> =", ">=").replace("< =", "<=").replace("! =", "!=")


def _extract_string_literals(query: str) -> List[str]:
    return re.findall(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", query)


def _replace_values_with_slots(query: str) -> Tuple[List[str], Set[str]]:
    values: List[str] = []
    replaced = query

    for literal in _extract_string_literals(query):
        values.append(literal)
        replaced = replaced.replace(literal, VALUE_NUM_SYMBOL)

    numeric_pattern = re.compile(r"(?<![\w])[-+]?\d+(?:\.\d+)?(?![\w])")
    seen_numeric = set()
    for match in numeric_pattern.finditer(replaced):
        value = match.group(0)
        if value not in seen_numeric:
            values.append(value)
            seen_numeric.add(value)
    replaced = numeric_pattern.sub(VALUE_NUM_SYMBOL, replaced)

    tokens = postprocess(replaced).strip().split()
    return [token.lower() for token in tokens], set(values)


def plugin(query_value_replaced: List[str], values_in_order: List[str]) -> str:
    query_w_values = query_value_replaced[:]
    value_idx = [idx for idx, token in enumerate(query_value_replaced) if token == VALUE_NUM_SYMBOL]
    assert len(value_idx) == len(values_in_order)
    for idx, value in zip(value_idx, values_in_order):
        query_w_values[idx] = value
    return " ".join(query_w_values)


def plugin_all_permutations(query_value_replaced: List[str], values: Set[str]) -> Iterator[str]:
    num_slots = len([token for token in query_value_replaced if token == VALUE_NUM_SYMBOL])
    if num_slots == 0:
        yield " ".join(query_value_replaced)
        return
    for combo in itertools.product(*[list(values) for _ in range(num_slots)]):
        yield plugin(query_value_replaced, list(combo))


def get_all_preds_for_execution(gold: str, pred: str) -> Tuple[int, Iterator[str]]:
    _, gold_values = _replace_values_with_slots(gold)
    pred_query_value_replaced, _ = _replace_values_with_slots(pred)
    num_slots = len([token for token in pred_query_value_replaced if token == VALUE_NUM_SYMBOL])
    num_alternatives = len(gold_values) ** num_slots
    return num_alternatives, plugin_all_permutations(pred_query_value_replaced, gold_values)


def remove_distinct(query: str) -> str:
    return re.sub(r"\bdistinct\b", "", query, flags=re.IGNORECASE)
