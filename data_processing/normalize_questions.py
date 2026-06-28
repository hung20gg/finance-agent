"""Normalize question_raw across data_mix_v2 jsonl files.

Two transformations, both rule-based (no LLM, no DB call needed):

1. Replace stray English macro phrases ("GNI per capita", "GDP growth") with
   their Vietnamese equivalent.
2. Augment ticker/country-code mentions: with probability AUG_PROB, swap the
   literal code (e.g. "CTG", "CHN") for a Vietnamese display name (company
   full name / short name, or country name) so the model sees more than one
   surface form per entity and is less likely to rote-memorize the code.

`answer`, `entities`, and all other metadata are left untouched -- only
`question_raw` is rewritten. Original files are not overwritten; outputs are
written as `<name>.norm.jsonl` next to the source.
"""
import csv
import json
import random
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data_mix_v2"
COMPANY_CSV = (
    Path(__file__).parent.parent
    / "data_collection"
    / "financial_statement"
    / "transform"
    / "metadata"
    / "df_company_info_v2.csv"
)
SEED = 42
AUG_PROB = 0.4

MACRO_PHRASE_VN = {
    "GNI per capita": "GNI bình quân đầu người",
    "GDP growth": "tăng trưởng GDP",
}

COUNTRY_VN = {
    "CAN": "Canada",
    "CHN": "Trung Quốc",
    "DEU": "Đức",
    "FRA": "Pháp",
    "GBR": "Anh",
    "IND": "Ấn Độ",
    "JPN": "Nhật Bản",
    "KOR": "Hàn Quốc",
    "SGP": "Singapore",
    "THA": "Thái Lan",
    "USA": "Mỹ",
    "VNM": "Việt Nam",
}


def load_company_map():
    company_map = {}
    with open(COMPANY_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = row["stock_code"].strip()
            if not code:
                continue
            names = [row.get("company_name", "").strip(), row.get("short_name", "").strip()]
            company_map[code] = [n for n in names if n]
    return company_map


def replace_macro_phrases(text):
    for en, vi in MACRO_PHRASE_VN.items():
        text = re.sub(re.escape(en), vi, text, flags=re.IGNORECASE)
    return text


def candidate_codes(row, company_map):
    """Return codes worth augmenting, tagged as 'country' or 'ticker'.

    A code like "SGP" is ambiguous: it is both the ISO code for Singapore and
    the ticker for "Cang Sai Gon". Disambiguate using question_family (macro
    family => country) or, when that metadata is absent (test_bo_sung.jsonl),
    the literal SQL filter (`country = 'SGP'` vs `stock_code = 'SGP'`).
    """
    is_macro = row.get("question_family") == "macro"
    sql = str(row.get("extra_info", {}).get("sql", ""))

    def kind_for(code):
        if is_macro and code in COUNTRY_VN:
            return "country"
        if re.search(rf"country\s*=\s*'{re.escape(code)}'", sql):
            return "country"
        if re.search(rf"stock_code\s*=\s*'{re.escape(code)}'", sql):
            return "ticker"
        if code in COUNTRY_VN and code not in company_map:
            return "country"
        if code in company_map:
            return "ticker"
        return None

    entities = row.get("entities")
    if entities:
        codes = [e for e in entities if e in company_map or e in COUNTRY_VN]
    else:
        # test_bo_sung.jsonl has no `entities` field: scan tokens instead.
        tokens = set(re.findall(r"\b[A-Z]{3,4}\b", row.get("question_raw", "")))
        codes = [t for t in tokens if t in company_map or t in COUNTRY_VN]

    tagged = []
    for code in codes:
        kind = kind_for(code)
        if kind:
            tagged.append((code, kind))
    return tagged


def augment_entity_mentions(text, tagged_codes, rng):
    for code, kind in tagged_codes:
        if rng.random() >= AUG_PROB:
            continue
        if kind == "country":
            display_options = [COUNTRY_VN[code]]
        else:
            display_options = COMPANY_MAP.get(code, [])
        if not display_options:
            continue
        display = rng.choice(display_options)
        text = re.sub(rf"\b{re.escape(code)}\b", display, text, count=1)
    return text


def normalize_row(row, rng):
    question_raw = row.get("question_raw", "")
    question_raw = replace_macro_phrases(question_raw)
    tagged_codes = candidate_codes(row, COMPANY_MAP)
    question_raw = augment_entity_mentions(question_raw, tagged_codes, rng)
    new_row = dict(row)
    new_row["question_raw"] = question_raw
    return new_row


def process_file(path, rng):
    out_path = path.with_suffix(".norm.jsonl")
    n = 0
    with open(path, encoding="utf-8") as fin, open(out_path, "w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            row = json.loads(line)
            new_row = normalize_row(row, rng)
            fout.write(json.dumps(new_row, ensure_ascii=False) + "\n")
            n += 1
    print(f"{path.name} -> {out_path.name}: {n} rows")


def main():
    global COMPANY_MAP
    COMPANY_MAP = load_company_map()
    rng = random.Random(SEED)

    for name in ["train.jsonl", "val.jsonl", "test.jsonl", "test_bo_sung.jsonl", "test_final.jsonl"]:
        path = DATA_DIR / name
        if path.exists():
            process_file(path, rng)


if __name__ == "__main__":
    main()
