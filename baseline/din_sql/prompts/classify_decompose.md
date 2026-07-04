# For the given question, classify it as EASY, NON-NESTED, or NESTED based on nested queries and JOIN.

Follow the DIN-SQL classification and decomposition module exactly:
if need nested queries: predict NESTED
elif need JOIN and do not need nested queries: predict NON-NESTED
elif do not need JOIN and do not need nested queries: predict EASY

Definitions:
- EASY: single-table SQL without JOIN and without nested subqueries or set operations.
- NON-NESTED: SQL needs JOIN but does not need nested subqueries or set operations.
- NESTED: SQL needs subqueries, CTE decomposition, IN, NOT IN, EXISTS, aggregate subqueries, INTERSECT, UNION, EXCEPT, or procedural sub-questions. It may also need JOIN.

For NESTED questions, decompose the problem into the sub-questions whose SQL results are needed before writing the final SQL.

Current date: {current_time}

Database schema and Foreign keys:
{schema_context}

Few-shot DIN-SQL examples:
{examples_text}

Question:
{question}

Schema_links:
{schema_links}

Return only valid JSON with this shape:
{
  "reasoning": "Let's think step by step. The SQL query needs these tables = [...]. ...",
  "label": "EASY | NON-NESTED | NESTED",
  "join_tables": ["table_name"],
  "sub_questions": ["sub-question text"]
}
