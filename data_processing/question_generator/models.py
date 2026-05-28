import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .const import INDEX_NAMES, METRIC_DISPLAY


QUESTION_TYPE_PATTERNS: Tuple[Tuple[str, str], ...] = (
    # CalculateQuestionMixin
    (r"^company_direct_.+$", "company_direct"),
    (r"^industry_avg_direct_.+$", "industry_avg_direct"),
    (r"^company_daily_.+$", "company_daily"),
    (r"^company_month_direct_.+$", "company_month_direct"),
    (r"^(index|commodity)_direct_.+$", r"\1_direct"),
    (r"^company_yearly_ema20_ema200_cross_count$", "company_yearly_ema20_ema200_cross_count"),
    (r"^company_yearly_.+$", "company_yearly"),
    (r"^company_trailing_4q_.+$", "company_trailing_4q"),

    # CompareQuestionMixin
    (r"^company_vs_company_winner_.+$", "company_vs_company_winner"),
    (r"^company_vs_company_diff_.+$", "company_vs_company_diff"),
    (r"^company_period_diff_.+$", "company_period_diff"),
    (r"^stock_vs_benchmark_direction$", "stock_vs_benchmark_direction"),
    (r"^stock_vs_benchmark_diff$", "stock_vs_benchmark_diff"),
    (r"^company_vs_industry_avg_diff_.+$", "company_vs_industry_avg_diff"),
    (r"^stock_vs_commodity_diff$", "stock_vs_commodity_diff"),
    (r"^company_vs_industry_total_share_pct_.+$", "company_vs_industry_total_share_pct"),
    (r"^industry_vs_industry_winner_.+$", "industry_vs_industry_winner"),
    (r"^industry_vs_industry_diff_.+$", "industry_vs_industry_diff"),
    (r"^company_vs_company_yearly_diff_.+$", "company_vs_company_yearly_diff"),
    (r"^company_same_period_quarter_diff_.+$", "company_same_period_quarter_diff"),
    (r"^company_same_period_year_diff_.+$", "company_same_period_year_diff"),
    (r"^company_h2_vs_h1_diff_.+$", "company_h2_vs_h1_diff"),
    (r"^company_same_period_half_diff_.+$", "company_same_period_half_diff"),

    # DrilldownQuestionMixin
    (r"^company_(best|worst)_quarter_in_year_.+$", "company_best_worst_quarter_in_year"),
    (r"^industry_top\d+_.+$", "industry_top"),
    (r"^universe_top\d+_.+$", "universe_top"),
    (r"^(index|commodity)_top\d+_.+$", r"\1_top"),
    (r"^company_time_range_.+$", "company_time_range"),
    (r"^company_vs_benchmark_time_range$", "company_vs_benchmark_time_range"),
    (r"^company_vs_industry_time_range_.+$", "company_vs_industry_time_range"),
    (r"^visualize_industry_top10_bar_.+$", "visualize_industry_top10_bar"),
    (r"^visualize_industry_heatmap_return_pct$", "visualize_industry_heatmap_return_pct"),
    (r"^visualize_company_vs_industry_scatter_.+$", "visualize_company_vs_industry_scatter"),

    # RollupQuestionMixin
    (r"^industry_mean_.+$", "industry_mean"),
    (r"^industry_positive_count_.+$", "industry_positive_count"),
    (r"^peer_[^_]+_.+$", "peer_aggregate"),
    (r"^universe_positive_count_.+$", "universe_positive_count"),

    # MacroQuestionMixin
    (r"^macro_direct_.+$", "macro_direct"),
    (r"^macro_yoy_change_pct_.+$", "macro_yoy_change_pct"),
    (r"^macro_(best|worst)_year_.+$", "macro_best_worst_year"),
)


def infer_question_type(question_subtype: str, metrics: Optional[List[str]] = None) -> str:
    subtype = str(question_subtype or "")
    if subtype.startswith("ambiguous::"):
        subtype = subtype.split("::", 1)[1]

    for pattern, replacement in QUESTION_TYPE_PATTERNS:
        if re.match(pattern, subtype):
            return re.sub(pattern, replacement, subtype)

    metric_candidates = set(str(metric) for metric in (metrics or []) if metric is not None)
    metric_candidates.update(str(metric) for metric in METRIC_DISPLAY.keys())
    for metric in sorted(metric_candidates, key=len, reverse=True):
        suffix = f"_{metric}"
        if subtype.endswith(suffix):
            return subtype[: -len(suffix)]

    return subtype


@dataclass
class GeneratorConfig:
    project_table_prefix: str = "neusolution.ktln"
    key_path: Optional[str] = None
    output_dir: str = "data_mix_v4"
    output_format: str = "json"
    seed: int = 42
    start_date: str = "2023-06-01"
    max_stocks: int = 150
    total_target_samples: int = 22000
    ambiguous_ratio: float = 0.10

    ratio_calculate: float = 0.28
    ratio_compare: float = 0.32
    ratio_roll_up: float = 0.20
    ratio_drill_down: float = 0.20
    ratio_macro: float = 0.08

    train_end: str = "2025-06-30"
    val_end: str = "2025-09-30"
    val_target_size: int = 2000
    test_target_size: int = 2000

    paraphrase_per_candidate: int = 2
    top_k_values: Tuple[int, int] = (5, 10)
    stock_daily_max_ratio: float = 0.05

    omit_answer_for_complex: bool = True
    answerless_modes: Tuple[str, ...] = ("visualize",)

    index_names: List[str] = field(default_factory=lambda: INDEX_NAMES.copy())
    commodity_allowlist: Optional[List[str]] = None


@dataclass
class PostgresGeneratorConfig:
    postgres_url: Optional[str] = None
    output_dir: str = "data_mix_v5"
    output_format: str = "json"
    seed: int = 42
    start_date: str = "2023-06-01"
    max_stocks: int = 150
    total_target_samples: int = 22000
    ambiguous_ratio: float = 0.10

    ratio_calculate: float = 0.28
    ratio_compare: float = 0.32
    ratio_roll_up: float = 0.20
    ratio_drill_down: float = 0.20
    ratio_macro: float = 0.08

    train_end: str = "2025-06-30"
    val_end: str = "2025-09-30"
    val_target_size: int = 2000
    test_target_size: int = 2000

    paraphrase_per_candidate: int = 2
    top_k_values: Tuple[int, int] = (5, 10)
    stock_daily_max_ratio: float = 0.05

    omit_answer_for_complex: bool = True
    answerless_modes: Tuple[str, ...] = ("top10", "time_range", "visualize")

    index_names: List[str] = field(default_factory=lambda: INDEX_NAMES.copy())
    commodity_allowlist: Optional[List[str]] = None


@dataclass
class QuestionRecord:
    question_raw: str
    answer_type: str
    answer: Any
    question_family: str
    question_subtype: str
    ambiguity: str
    time_asked: str
    gap: int
    data_cutoff: str
    entities: List[str]
    metrics: List[str]
    periods: List[str]
    sources: List[str]
    reasoning_hops: int
    extra_info: Dict[str, Any]

    def to_json(self) -> Dict[str, Any]:
        row = asdict(self)
        out: Dict[str, Any] = {}
        for key, value in row.items():
            if key == "question_subtype":
                out["question_type"] = infer_question_type(self.question_subtype, self.metrics)
            out[key] = value
        return out
