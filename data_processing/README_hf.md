---
language:
- vi
task_categories:
- question-answering
dataset_info:
  features:
  - name: id
    dtype: string
  - name: question
    dtype: string
  - name: answer_type
    dtype: string
  - name: answer
    dtype: string
  - name: time_asked
    dtype: string
  - name: sources
    sequence: string
  - name: data_source
    dtype: string
  - name: reward_model
    struct:
    - name: style
      dtype: string
    - name: ground_truth
      dtype: string
  - name: extra_info
    struct:
    - name: gap
      dtype: int64
    - name: data_cutoff
      dtype: string
    - name: reasoning_hops
      dtype: int64
    - name: entities
      sequence: string
    - name: metrics
      sequence: string
    - name: periods
      sequence: string
    - name: question_family
      dtype: string
    - name: question_subtype
      dtype: string
    - name: ambiguity
      dtype: string
    - name: result_columns
      sequence: string
    - name: value_a
      dtype: float64
    - name: value_b
      dtype: float64
    - name: current
      dtype: float64
    - name: previous
      dtype: float64
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

# Financial Forecast Dataset

Vietnamese finance QA dataset focused on company metrics and comparisons.

## Columns
- `id`: Unique identifier
- `question`: Formatted question
- `question_raw`: Raw question text
- `answer_type`: Type of answer (e.g., `entity`)
- `answer`: The numerical answer
- `time_asked`: Date the question was asked
- `sources`: Data sources (e.g., `company_quarter`)
- `data_source`: Identifier for the data source pipeline (e.g., `finance-sql`)
- `reward_model`: Reward model config containing:
    - `style`: Reward style (e.g., `rule`)
    - `ground_truth`: The ground truth value used for reward computation
- `extra_info`: Metadata containing:
    - `gap`: Time gap in periods
    - `data_cutoff`: Data cutoff date
    - `reasoning_hops`: Number of reasoning steps
    - `entities`: List of companies/entities involved
    - `metrics`: List of financial metrics involved
    - `periods`: List of time periods involved
    - `question_family`: Category of the question
    - `question_subtype`: Detailed subcategory
    - `ambiguity`: Ambiguity status
    - `value_a`, `value_b`, `current`, `previous`: Intermediate numerical values
