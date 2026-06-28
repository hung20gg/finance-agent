Chạy test MAC-SQL:

```bash
python baseline/mac-sql/evaluation/evaluation_finance.py \
  --dataset data_processing/data_mix_v5/test_clean.xlsx \
  --predictions data/eval_test_results_<model>.jsonl
```