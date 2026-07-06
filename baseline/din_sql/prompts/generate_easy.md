# Use the schema links to generate the PostgreSQL query for the question.

This is the DIN-SQL SQL generation module for the EASY class. Because this class does not need JOIN or nested queries, do not add an intermediate representation. Generate the final SQL directly from the question and schema links.

Current date: {current_time}

Database schema:
{schema_context}

Few-shot examples:
{examples_text}

Q: "{question}"
Schema_links: {schema_links}

Return only valid JSON with this shape:
{
  "reasoning": "Brief reasoning using the schema links.",
  "sql": "SELECT ..."
}
