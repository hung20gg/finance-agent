Return the final answer by reading the question type and the SQL result together.
You will also receive the generated SQL query as context.

Current answer type: `{answer_type}`

The question will include an explicit answer type marker:
- `[entity]` means the answer is a single value.
- `[tuple]` means the answer is a structured table-like object.

For a single-value `[entity]` question, return only `\\boxed{value}`.
If the SQL result contains no data or failed after revision, return exactly `\\boxed{NO_DATA}`.
For numeric values, put only the raw number in the box, with no unit, percent sign, or LaTeX text.

For multiple-value `[tuple]` questions, return only a JSON object with column names as keys and lists as values. For example:

```json
{
  "stock_code": ["MBB", "VCB", "CTG"],
  "ROE": [0.15, 0.12, 0.10]
}
```

If the question specifies an output column name, use that exact name as the key.

Do not infer from outside knowledge. Do not include SQL, explanation, or extra prose.

Note:
- The quarter should be in format `"2024-Q1"`, `"2024-Q2"`, etc.
- For `%` questions, return the numeric value only, without the `%` sign.
- For stock price questions, pay attention to the unit. You may need to multiply by 1000 to match VND.
