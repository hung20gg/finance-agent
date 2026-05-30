import random
from typing import Any, Dict, List

import pandas as pd

from .ambiguity import AmbiguityQuestionMixin
from .calculate import CalculateQuestionMixin
from .compare import CompareQuestionMixin
from .drilldown import DrilldownQuestionMixin
from .export import SamplingExportMixin
from .macro import MacroQuestionMixin
from .models import GeneratorConfig, QuestionRecord
from .rollup import RollupQuestionMixin
from .utils import _company_label


class QuestionGenerator(
    CalculateQuestionMixin,
    CompareQuestionMixin,
    RollupQuestionMixin,
    DrilldownQuestionMixin,
    MacroQuestionMixin,
    AmbiguityQuestionMixin,
    SamplingExportMixin,
):
    """Sinh câu hỏi từ các bảng trung gian."""

    def __init__(self, store: Dict[str, pd.DataFrame], config: GeneratorConfig):
        # Prevent any data >= 2026 from being used in generation
        for key, df in store.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                if "year" in df.columns:
                    df = df[pd.to_numeric(df["year"], errors="coerce") < 2026]
                if "time" in df.columns:
                    df = df[pd.to_datetime(df["time"], errors="coerce") < pd.Timestamp("2026-01-01")]
                if "datetime" in df.columns:
                    df = df[pd.to_datetime(df["datetime"], errors="coerce") < pd.Timestamp("2026-01-01")]
                store[key] = df

        self.store = store
        self.config = config
        self.rng = random.Random(config.seed)

        # Map metadata theo mã để gọi tên đúng kiểu doanh nghiệp.
        company_info = store.get("company_info", pd.DataFrame()).copy()
        if not company_info.empty and "stock_code" in company_info.columns:
            company_info["stock_code"] = company_info["stock_code"].astype(str)
            if "is_bank" not in company_info.columns:
                company_info["is_bank"] = False
            if "is_securities" not in company_info.columns:
                company_info["is_securities"] = False
            self.company_meta = company_info.drop_duplicates(subset=["stock_code"]).set_index("stock_code").to_dict("index")
        else:
            self.company_meta = {}

    def _company_label(self, stock_code: str, is_stock: bool = True) -> str:
        meta = self.company_meta.get(str(stock_code), {})
        prefix = "mã cổ phiếu " if is_stock else ""
        return prefix + _company_label(
            stock_code=str(stock_code),
            is_bank=bool(meta.get("is_bank", False)),
            is_securities=bool(meta.get("is_securities", False)),
        )

    def _is_stock_daily_question(self, record: QuestionRecord) -> bool:
        return "stock_daily" in set(record.sources or [])

    def _stock_daily_max_count(self) -> int:
        ratio = max(0.0, float(getattr(self.config, "stock_daily_max_ratio", 0.05) or 0.0))
        return int(max(0, self.config.total_target_samples) * ratio)

    def _limit_stock_daily_records(self, records: List[QuestionRecord]) -> List[QuestionRecord]:
        limit = self._stock_daily_max_count()
        if limit <= 0:
            return []
        records = list(records)
        self.rng.shuffle(records)
        return records[:limit]

    def generate(self) -> List[QuestionRecord]:
        clear_candidates: Dict[str, List[QuestionRecord]] = {
            "calculate": self.generate_calculate_questions(),
            "compare": self.generate_compare_questions(),
            "roll_up": self.generate_rollup_questions(),
            "drill_down": self.generate_drilldown_questions(),
            "macro": self.generate_macro_questions(),
        }
        sampled_clear = self._sample_clear_mix(clear_candidates)
        ambiguous = self.generate_ambiguous_questions(sampled_clear)
        final_records = sampled_clear + ambiguous
        self.rng.shuffle(final_records)
        return final_records

    # -----------------------------------------------------
    # Answer policy helpers
    # -----------------------------------------------------
    def _maybe_answer(self, mode: str, answer: Any) -> Any:
        # if self.config.omit_answer_for_complex and mode in set(self.config.answerless_modes):
        #     return None
        return answer

    def _common_metadata(self, **kwargs: Any) -> Dict[str, Any]:
        return dict(kwargs)
