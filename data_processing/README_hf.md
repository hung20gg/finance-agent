---
language:
- vi
task_categories:
- question-answering
dataset_info:
  features:
  - name: data_source
    dtype: string
  - name: prompt
    list:
    - name: role
      dtype: string
    - name: content
      dtype: string
  - name: ability
    dtype: string
  - name: reward_model
    struct:
    - name: style
      dtype: string
    - name: ground_truth
      struct:
      - name: mean
        dtype: float64
      - name: std
        dtype: float64
  - name: extra_info
    struct:
    - name: split
      dtype: string
    - name: index
      dtype: int64
    - name: time_asked
      dtype: string
    - name: gap
      dtype: int64
    - name: question_type
      dtype: string
    - name: std
      dtype: float64
    - name: id
      dtype: string
configs:
- config_name: default
  data_files:
  - split: train
    path: train.jsonl
  - split: val
    path: val.jsonl
  - split: test
    path: test.jsonl
---

# Financial Forecast Dataset (ktln)

Vietnamese finance QA dataset in chat format.

## Columns
- `data_source`: source tag (e.g. `ktln`)
- `prompt`: list of chat messages with `role` and `content`
- `ability`: e.g. `math`
- `reward_model.ground_truth`: numeric targets (`mean`, `std`)
- `extra_info`: metadata (split/index/time_asked/gap/question_type/std/id)
