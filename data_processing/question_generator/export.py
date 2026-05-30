import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from .const import FINANCIAL_NAMES, VN30_TICKERS
from .models import QuestionRecord, infer_question_type
from .utils import _count_by


FINANCIAL_ACCOUNT_METRICS = set(FINANCIAL_NAMES.keys())


class SamplingExportMixin:
    # -----------------------------------------------------
    # Sampling / split / export
    # -----------------------------------------------------
    def _sample_clear_mix(self, candidate_dict: Dict[str, List[QuestionRecord]]) -> List[QuestionRecord]:
        total_clear_target = max(1, int(self.config.total_target_samples * (1.0 - self.config.ambiguous_ratio)))
        weights = {
            "calculate": self.config.ratio_calculate,
            "compare": self.config.ratio_compare,
            "roll_up": self.config.ratio_roll_up,
            "drill_down": self.config.ratio_drill_down,
            "macro": self.config.ratio_macro,
        }
        norm = sum(weights.values())
        quotas = {k: max(1, int(total_clear_target * v / norm)) for k, v in weights.items()}

        sampled: List[QuestionRecord] = []
        stock_daily_remaining = self._stock_daily_max_count()

        def take_record(record: QuestionRecord) -> bool:
            nonlocal stock_daily_remaining
            if self._is_stock_daily_question(record):
                if stock_daily_remaining <= 0:
                    return False
                stock_daily_remaining -= 1
            sampled.append(record)
            return True

        for family, pool in candidate_dict.items():
            self.rng.shuffle(pool)
            selected_for_family = 0
            family_quota = quotas.get(family, 0)

            if family == "macro":
                selected_ids: Set[int] = set()
                split_buckets = {
                    split_name: [
                        record for record in pool
                        if self._target_split_for_record(record) == split_name
                    ]
                    for split_name in ["train", "val", "test"]
                }
                non_empty_splits = [
                    split_name for split_name in ["train", "val", "test"]
                    if split_buckets[split_name]
                ]
                base_quota = max(1, family_quota // max(1, len(non_empty_splits)))

                for split_name in non_empty_splits:
                    if selected_for_family >= family_quota:
                        break
                    split_quota = min(
                        base_quota,
                        family_quota - selected_for_family,
                        len(split_buckets[split_name]),
                    )
                    for record in self._select_coverage_items(split_buckets[split_name], split_quota):
                        if id(record) in selected_ids:
                            continue
                        if take_record(record):
                            selected_ids.add(id(record))
                            selected_for_family += 1

                leftovers = [record for record in pool if id(record) not in selected_ids]
                self.rng.shuffle(leftovers)
                for record in leftovers:
                    if selected_for_family >= family_quota:
                        break
                    if take_record(record):
                        selected_ids.add(id(record))
                        selected_for_family += 1
                continue

            if family == "calculate" and stock_daily_remaining > 0:
                daily_pool = [record for record in pool if self._is_stock_daily_question(record)]
                other_pool = [record for record in pool if not self._is_stock_daily_question(record)]
                self.rng.shuffle(daily_pool)
                self.rng.shuffle(other_pool)

                daily_quota = min(stock_daily_remaining, len(daily_pool), family_quota)
                for record in daily_pool[:daily_quota]:
                    if take_record(record):
                        selected_for_family += 1
                pool = other_pool

            for record in pool:
                if selected_for_family >= family_quota:
                    break
                if take_record(record):
                    selected_for_family += 1

        if len(sampled) < total_clear_target:
            leftovers: List[QuestionRecord] = []
            selected_ids = {id(x) for x in sampled}
            for pool in candidate_dict.values():
                leftovers.extend([x for x in pool if id(x) not in selected_ids])
            self.rng.shuffle(leftovers)
            for record in leftovers:
                if len(sampled) >= total_clear_target:
                    break
                take_record(record)

        self.rng.shuffle(sampled)
        return sampled

    def _is_priority_non_stock_question(self, record: QuestionRecord) -> bool:
        """Ưu tiên giữ các câu hỏi ngành, chỉ số, commodity trước khi downsample.

        Lưu ý: câu stock vs benchmark vẫn có index_market trong sources nhưng về bản chất
        vẫn là stock-related, nên không được xếp vào nhóm ưu tiên này.
        """
        subtype = str(record.question_subtype or "")
        sources = set(record.sources or [])

        # Câu có chuẩn ngành hoặc roll-up / drill-down theo ngành.
        if subtype.startswith("industry_") or "company_vs_industry" in subtype or subtype.startswith("visualize_industry_"):
            return True
        if "industry_avg_quarter" in sources:
            return True
        if str(record.extra_info.get("group_by", "")) == "industry":
            return True

        # Câu thuần chỉ số. Loại trừ các câu có company_quarter để tránh lẫn với stock-related.
        if (subtype.startswith("index_") or sources == {"index_market"}) and "company_quarter" not in sources:
            return True

        # Câu thuần commodity.
        if (subtype.startswith("commodity_") or sources == {"commodity_market"}) and "company_quarter" not in sources:
            return True

        if subtype.startswith("macro_") or sources in [{"macro_quarter"}, {"macro_yearly"}]:
            return True

        return False

    def _is_macro_question(self, record: QuestionRecord) -> bool:
        return record.question_family == "macro" or "macro_yearly" in set(record.sources or [])

    def _macro_split_year(self, record: QuestionRecord) -> Optional[int]:
        years: List[int] = []
        for period in record.periods or []:
            value = str(period)
            if len(value) >= 4 and value[:4].isdigit():
                years.append(int(value[:4]))
        if years:
            return max(years)
        return None

    def _target_split_for_record(self, record: QuestionRecord) -> str:
        if self._is_macro_question(record):
            year = self._macro_split_year(record)
            if year is not None:
                if year <= 2022:
                    return "train"
                if year == 2023:
                    return "val"
                return "test"

        asked = datetime.strptime(record.time_asked, "%Y-%m-%d")
        train_end = datetime.strptime(self.config.train_end, "%Y-%m-%d")
        val_end = datetime.strptime(self.config.val_end, "%Y-%m-%d")
        if asked <= train_end:
            return "train"
        if asked <= val_end:
            return "val"
        return "test"

    def _vn30_weight(self, record: QuestionRecord) -> float:
        """Tăng trọng số x5 cho câu stock-related có dính mã VN30.

        Dùng cho bước random downsample ở val/test sau khi đã giữ lại nhóm câu hỏi
        ngành, chỉ số và commodity. Nếu một câu không phải stock-related hoặc không
        chứa mã VN30 nào thì trọng số giữ nguyên bằng 1.
        """
        if self._is_priority_non_stock_question(record):
            return 1.0

        entities = {str(x) for x in (record.entities or [])}
        if entities & VN30_TICKERS:
            return 5.0

        stock_list = record.extra_info.get("stock_list")
        if isinstance(stock_list, list) and {str(x) for x in stock_list} & VN30_TICKERS:
            return 5.0

        top_entities = record.extra_info.get("top_entities")
        if isinstance(top_entities, list) and {str(x) for x in top_entities} & VN30_TICKERS:
            return 5.0

        return 1.0

    def _weighted_sample_without_replacement(self, items: List[QuestionRecord], k: int, weight_fn) -> List[QuestionRecord]:
        """Weighted random sampling không hoàn lại.

        Dùng biến thể Efraimidis-Spirakis: mỗi phần tử nhận một key ngẫu nhiên phụ thuộc
        vào trọng số; trọng số càng lớn thì xác suất nằm trong top-k càng cao.
        """
        if k <= 0:
            return []
        if len(items) <= k:
            return list(items)

        scored: List[Tuple[float, QuestionRecord]] = []
        for item in items:
            weight = max(float(weight_fn(item)), 1e-9)
            key = self.rng.random() ** (1.0 / weight)
            scored.append((key, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:k]]

    def _coverage_keys(self, record: QuestionRecord) -> Set[Tuple[str, str]]:
        question_type = infer_question_type(record.question_subtype, record.metrics)

        keys: Set[Tuple[str, str]] = set()
        for key_type, value in [
            ("family", record.question_family),
            ("question_type", question_type),
            ("answer_type", record.answer_type),
            ("ambiguity", record.ambiguity),
        ]:
            if value:
                keys.add((key_type, str(value)))

        for source in record.sources or []:
            keys.add(("source", str(source)))

        for metric in record.metrics or []:
            metric = str(metric)
            if metric in FINANCIAL_ACCOUNT_METRICS:
                keys.add(("financial_metric", metric))
            else:
                keys.add(("metric", metric))

        return keys

    def _coverage_priority(self, key: Tuple[str, str]) -> Tuple[int, str, str]:
        order = {
            "family": 0,
            "source": 1,
            "financial_metric": 2,
            "question_type": 3,
            "metric": 4,
            "answer_type": 5,
            "ambiguity": 6,
        }
        return order.get(key[0], 99), key[0], key[1]

    def _coverage_score(self, keys: Set[Tuple[str, str]], uncovered: Set[Tuple[str, str]]) -> int:
        weights = {
            "family": 8,
            "source": 6,
            "financial_metric": 6,
            "question_type": 4,
            "metric": 3,
            "answer_type": 2,
            "ambiguity": 1,
        }
        return sum(weights.get(key_type, 1) for key_type, _ in keys & uncovered)

    def _all_coverage_keys(self, items: List[QuestionRecord]) -> Set[Tuple[str, str]]:
        keys: Set[Tuple[str, str]] = set()
        for item in items:
            keys.update(self._coverage_keys(item))
        return keys

    def _select_coverage_items(
        self,
        items: List[QuestionRecord],
        target_size: int,
        required_keys: Optional[Set[Tuple[str, str]]] = None,
    ) -> List[QuestionRecord]:
        if target_size <= 0 or not items:
            return []

        selected: List[QuestionRecord] = []
        selected_ids: Set[int] = set()
        keys_by_id = {id(item): self._coverage_keys(item) for item in items}
        uncovered = set(required_keys) if required_keys is not None else set().union(*keys_by_id.values())

        for key in sorted(uncovered.copy(), key=self._coverage_priority):
            if len(selected) >= target_size:
                break
            if key not in uncovered:
                continue

            candidates = [
                item for item in items
                if id(item) not in selected_ids and key in keys_by_id[id(item)]
            ]
            if not candidates:
                uncovered.discard(key)
                continue

            best = max(
                candidates,
                key=lambda item: (
                    self._coverage_score(keys_by_id[id(item)], uncovered),
                    self._vn30_weight(item),
                    self.rng.random(),
                ),
            )
            selected.append(best)
            selected_ids.add(id(best))
            uncovered -= keys_by_id[id(best)]

        return selected

    def _downsample_split(self, items: List[QuestionRecord], target_size: int) -> List[QuestionRecord]:
        """Cắt bớt split theo rule ưu tiên user yêu cầu.

        Rule:
        1. Giữ coverage theo family, question_type, source, metric/tài khoản.
        2. Giữ câu ngành, chỉ số, commodity trước.
        3. Phần còn lại lấy weighted random, trong đó câu stock-related có mã VN30
           được nhân trọng số 5 lần.
        """
        if target_size <= 0 or len(items) <= target_size:
            return list(items)

        selected = self._select_coverage_items(items, target_size)
        selected_ids = {id(x) for x in selected}
        remaining = target_size - len(selected)
        if remaining <= 0:
            self.rng.shuffle(selected)
            return selected

        remaining_items = [x for x in items if id(x) not in selected_ids]
        macro_items = [x for x in remaining_items if self._is_macro_question(x)]
        if len(macro_items) >= remaining:
            selected.extend(self._weighted_sample_without_replacement(macro_items, remaining, lambda _: 1.0))
            self.rng.shuffle(selected)
            return selected

        selected.extend(macro_items)
        remaining = target_size - len(selected)
        selected_ids = {id(x) for x in selected}
        remaining_items = [x for x in items if id(x) not in selected_ids]
        priority_items = [x for x in remaining_items if self._is_priority_non_stock_question(x)]
        other_items = [x for x in remaining_items if not self._is_priority_non_stock_question(x)]

        if len(priority_items) >= remaining:
            selected.extend(self._weighted_sample_without_replacement(priority_items, remaining, lambda _: 1.0))
        else:
            selected.extend(priority_items)
            remaining = target_size - len(selected)
            selected.extend(self._weighted_sample_without_replacement(other_items, remaining, self._vn30_weight))

        self.rng.shuffle(selected)
        return selected

    def _limit_stock_daily_share(self, items: List[QuestionRecord]) -> List[QuestionRecord]:
        ratio = max(0.0, float(getattr(self.config, "stock_daily_max_ratio", 0.05) or 0.0))
        if ratio >= 1.0 or not items:
            return list(items)

        stock_daily_items = [x for x in items if self._is_stock_daily_question(x)]
        if not stock_daily_items:
            return list(items)

        other_items = [x for x in items if not self._is_stock_daily_question(x)]
        max_stock_daily = int((ratio * len(other_items)) / (1.0 - ratio))
        if len(stock_daily_items) <= max_stock_daily:
            return list(items)

        self.rng.shuffle(stock_daily_items)
        selected = other_items + stock_daily_items[:max_stock_daily]
        self.rng.shuffle(selected)
        return selected

    def _ensure_eval_split_coverage(
        self,
        split_dict: Dict[str, List[QuestionRecord]],
        split_name: str,
        all_records: List[QuestionRecord],
        target_size: int,
    ) -> None:
        if target_size <= 0:
            return

        current_keys = self._all_coverage_keys(split_dict[split_name])
        target_keys = self._all_coverage_keys(all_records)
        missing_keys = target_keys - current_keys
        if not missing_keys:
            return

        other_eval_ids = {
            id(item)
            for name, items in split_dict.items()
            if name in {"val", "test"} and name != split_name
            for item in items
        }
        current_ids = {id(item) for item in split_dict[split_name]}
        candidates = [
            item for item in all_records
            if id(item) not in current_ids
            and id(item) not in other_eval_ids
            and (not self._is_macro_question(item) or self._target_split_for_record(item) == split_name)
            and self._coverage_keys(item) & missing_keys
        ]
        additions = self._select_coverage_items(
            candidates,
            max(target_size, len(missing_keys)),
            required_keys=missing_keys,
        )
        if not additions:
            return

        expanded = split_dict[split_name] + additions
        split_dict[split_name] = self._downsample_split(expanded, target_size)
        kept_addition_ids = {id(item) for item in split_dict[split_name]} & {id(item) for item in additions}
        for name in list(split_dict.keys()):
            if name != split_name:
                split_dict[name] = [item for item in split_dict[name] if id(item) not in kept_addition_ids]

    def split_records(self, records: List[QuestionRecord]) -> Dict[str, List[QuestionRecord]]:
        split_dict = {"train": [], "val": [], "test": []}
        self.rng.shuffle(records)
        for record in records:
            split_dict[self._target_split_for_record(record)].append(record)

        # Val và test bị khóa kích thước tối đa 2k theo yêu cầu.
        split_dict["val"] = self._downsample_split(split_dict["val"], self.config.val_target_size)
        split_dict["test"] = self._downsample_split(split_dict["test"], self.config.test_target_size)
        self._ensure_eval_split_coverage(split_dict, "val", records, self.config.val_target_size)
        self._ensure_eval_split_coverage(split_dict, "test", records, self.config.test_target_size)
        split_dict = {
            split_name: self._limit_stock_daily_share(items)
            for split_name, items in split_dict.items()
        }
        return split_dict

    def export_records(self, split_dict: Dict[str, List[QuestionRecord]]) -> None:
        os.makedirs(self.config.output_dir, exist_ok=True)
        formats = self._parse_output_formats()
        rows_by_split = {
            split_name: self._records_to_rows(split_name, items)
            for split_name, items in split_dict.items()
        }

        if "json" in formats:
            self._export_jsonl(rows_by_split)
        if "csv" in formats:
            self._export_csv(rows_by_split)
        if "excel" in formats:
            self._export_excel(rows_by_split)

        self._export_summary(split_dict)

    def export_jsonl(self, split_dict: Dict[str, List[QuestionRecord]]) -> None:
        self.export_records(split_dict)

    def _parse_output_formats(self) -> List[str]:
        allowed = {"json", "excel", "csv"}
        raw = str(getattr(self.config, "output_format", "json") or "json")
        formats = []
        for item in raw.split(","):
            fmt = item.strip().lower()
            if not fmt:
                continue
            if fmt not in allowed:
                raise ValueError(f"Unknown output format: {fmt}. Expected one of: json, excel, csv")
            if fmt not in formats:
                formats.append(fmt)
        return formats or ["json"]

    def _records_to_rows(self, split_name: str, items: List[QuestionRecord]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for idx, item in enumerate(items):
            row = item.to_json()
            row["id"] = f"{split_name}-{idx:08d}"
            rows.append(row)
        return rows

    def _flatten_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        flat_rows: List[Dict[str, Any]] = []
        for row in rows:
            flat_row = {}
            for key, value in row.items():
                if isinstance(value, (list, dict)):
                    flat_row[key] = json.dumps(value, ensure_ascii=False)
                else:
                    flat_row[key] = value
            flat_rows.append(flat_row)
        return flat_rows

    def _export_jsonl(self, rows_by_split: Dict[str, List[Dict[str, Any]]]) -> None:
        for split_name, rows in rows_by_split.items():
            path = os.path.join(self.config.output_dir, f"{split_name}.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _export_csv(self, rows_by_split: Dict[str, List[Dict[str, Any]]]) -> None:
        for split_name, rows in rows_by_split.items():
            path = os.path.join(self.config.output_dir, f"{split_name}.csv")
            pd.DataFrame(self._flatten_rows(rows)).to_csv(path, index=False)

    def _export_excel(self, rows_by_split: Dict[str, List[Dict[str, Any]]]) -> None:
        path = os.path.join(self.config.output_dir, "questions.xlsx")
        with pd.ExcelWriter(path) as writer:
            for split_name, rows in rows_by_split.items():
                pd.DataFrame(self._flatten_rows(rows)).to_excel(writer, sheet_name=split_name[:31], index=False)

    def _export_summary(self, split_dict: Dict[str, List[QuestionRecord]]) -> None:
        summary = {
            split: {
                "count": len(items),
                "ambiguous": sum(1 for x in items if x.ambiguity == "ambiguous"),
                "families": _count_by(items, key=lambda r: r.question_family),
                "question_types": _count_by(items, key=lambda r: infer_question_type(r.question_subtype, r.metrics)),
                "subtypes": _count_by(items, key=lambda r: r.question_subtype),
                "sources": _count_by([source for x in items for source in x.sources], key=lambda x: x),
                "metrics": _count_by([metric for x in items for metric in x.metrics], key=lambda x: x),
                "financial_metrics": _count_by(
                    [metric for x in items for metric in x.metrics if metric in FINANCIAL_ACCOUNT_METRICS],
                    key=lambda x: x,
                ),
                "macro_years": _count_by(
                    [self._macro_split_year(x) for x in items if self._is_macro_question(x) and self._macro_split_year(x) is not None],
                    key=lambda x: str(x),
                ),
                "answer_types": _count_by(items, key=lambda r: r.answer_type),
                "answer_missing": sum(1 for x in items if x.answer is None),
                "stock_daily": sum(1 for x in items if self._is_stock_daily_question(x)),
            }
            for split, items in split_dict.items()
        }
        with open(os.path.join(self.config.output_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    def _build_record(
        self,
        question_raw: str,
        answer_type: str,
        answer: Any,
        family: str,
        subtype: str,
        ambiguity: str,
        time_asked: str,
        gap: int,
        data_cutoff: str,
        entities: List[str],
        metrics: List[str],
        periods: List[str],
        sources: List[str],
        reasoning_hops: int,
        extra_info: Dict[str, Any],
    ) -> QuestionRecord:
        return QuestionRecord(
            question_raw=question_raw,
            answer_type=answer_type,
            answer=answer,
            question_family=family,
            question_subtype=subtype,
            ambiguity=ambiguity,
            time_asked=time_asked,
            gap=gap,
            data_cutoff=data_cutoff,
            entities=list(dict.fromkeys([str(x) for x in entities if x is not None])),
            metrics=list(dict.fromkeys([str(x) for x in metrics if x is not None])),
            periods=list(dict.fromkeys([str(x) for x in periods if x is not None])),
            sources=list(dict.fromkeys([str(x) for x in sources if x is not None])),
            reasoning_hops=reasoning_hops,
            extra_info=extra_info,
        )
