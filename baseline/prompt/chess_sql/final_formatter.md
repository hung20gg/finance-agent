Return the final answer for the user.

For a single-value `[entity]` question, return only `\boxed{value}`.
If the SQL result contains no data or failed after revision, return exactly `\boxed{NO_DATA}`.
For numeric values, put only the raw number in the box, with no unit, percent sign, or LaTeX text.

For multiple-value `[tuple]` questions, return only a JSON object with column names as keys and lists as values.

Do not include SQL, explanation, or extra prose.
