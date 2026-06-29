Chạy test MAC-SQL:

```bash
python -m baseline.mac_sql.evaluation.evaluation_finance \
  --dataset data_processing/data_mix_v5/test_clean.xlsx \
  --predictions data/eval_test_results_<model>.jsonl
```
