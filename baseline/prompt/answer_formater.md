For question asking for single value (either text or number): Return only the value directly in \\boxed{}.

If the SQL result contains one numeric answer, put only the raw number in \\boxed{} with no unit, percent sign, LaTeX text, explanation, or SQL query. Example: use \\boxed{8.56367}, not \\boxed{8.56367\%} and not \\boxed{8.56367 \text{percent}}.

If the SQL result is failed, empty, or contains no data, do not infer from outside knowledge and do not guess. Return exactly \\boxed{NO_DATA}.

For question asking for multiple values: Return a list of values in JSON format, with the column name as key and the value as list. If user provides a specific column name, use that as the key. For example:

```json
{
  "stock_code": ["MBB", "VCB", "CTG"],
  "ROE": [0.15, 0.12, 0.10]
}
```

Do not return the SQL query unless the question asks for it.

That being said, your final answer should cover all the information required by the user.

Note:
- the quater should be in format "2024-Q1", "2024-Q2", etc
- When return answer in the \\boxed{}, you should only return the stock_code/index_name/indicator_name or any other name in short form, exactly from the database (MBB instead of Ngân hàng MB or anything else)
- If user ask for specific column name, you should name the column in the output as they ask. For example, if user ask for "What is the average PE ratio? column: [A]", you should name the columns as A in the SQL query and result.
- With % value questions, always answer with the percentage value only, without the % sign.
- With stock price, notice the unit. You might need to * 1000 to match with the actual VND unit.