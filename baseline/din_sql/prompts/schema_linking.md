# Find the schema_links for generating a PostgreSQL query for the question based on the database schema and Foreign keys.

Follow the DIN-SQL schema linking module exactly:
1. Think step by step.
2. Identify every table column mentioned or implied by the question.
3. Identify foreign-key links required to connect those columns.
4. Identify possible entity names, stock codes, metric codes, index names, country names, commodity names, years, quarters, and other cell values mentioned in the question.
5. Produce the final Schema_links list.

Use the current date when interpreting relative time expressions: {current_time}.

Database schema and Foreign keys:
{schema_context}

Few-shot DIN-SQL examples:
{examples_text}

Question:
{question}

Return only valid JSON with this shape:
{
  "reasoning": "Let's think step by step. ...",
  "schema_links": ["table.column", "table.column = other_table.column", "literal value"]
}
