from typing import List

from .models import QuestionRecord
from .utils import _choose_distinct


class AmbiguityQuestionMixin:
    # -----------------------------------------------------
    # Controlled ambiguous questions
    # -----------------------------------------------------
    def generate_ambiguous_questions(self, clear_records: List[QuestionRecord]) -> List[QuestionRecord]:
        target = max(1, int(len(clear_records) * self.config.ambiguous_ratio))
        pool = [
            r for r in clear_records
            if r.question_family in {"calculate", "compare", "roll_up", "drill_down"}
            and not self._is_stock_daily_question(r)
        ]
        if not pool:
            return []
        selected = _choose_distinct(pool, min(target, len(pool)), self.rng)
        ambiguous: List[QuestionRecord] = []
        for base in selected:
            ambiguous.append(self._build_record(
                question_raw=self._ambiguify_question(base.question_raw),
                answer_type=base.answer_type,
                answer=base.answer,
                family=base.question_family,
                subtype=f"ambiguous::{base.question_subtype}",
                ambiguity="ambiguous",
                time_asked=base.time_asked,
                gap=base.gap,
                data_cutoff=base.data_cutoff,
                entities=base.entities,
                metrics=base.metrics,
                periods=base.periods,
                sources=base.sources,
                reasoning_hops=base.reasoning_hops,
                extra_info={
                    **base.extra_info,
                    "resolved_from_clear_question": base.question_raw,
                    "ambiguity_rule": "controlled_ambiguity",
                },
            ))
        return ambiguous

    def _ambiguify_question(self, q: str) -> str:
        replacements = [
            ("VNINDEX", "thị trường chung"),
            ("VN30", "rổ bluechip"),
            ("lợi nhuận ròng", "lợi nhuận"),
            ("tỷ suất sinh lời", "mức sinh lời"),
            ("trung bình ngành", "mức trung bình của ngành"),
            ("quý 1 năm", "quý đầu năm"),
            ("quý 4 năm", "quý cuối năm"),
            ("công ty", "mã"),
        ]
        applied = False
        for src, dst in replacements:
            if src in q and self.rng.random() < 0.55:
                q = q.replace(src, dst)
                applied = True
        if not applied:
            if "bao nhiêu" in q:
                q = q.replace("bao nhiêu", "cỡ nào", 1)
            elif "Trong " in q:
                q = q.replace("Trong ", "Ở ", 1)
            else:
                q = f"Xét theo dữ liệu gần nhất đủ dùng, {q[0].lower() + q[1:]}"
        return q
