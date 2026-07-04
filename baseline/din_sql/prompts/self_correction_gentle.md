For the given question, database schema, and SQL query, check whether the SQL has any potential issues. If it is already correct, return it unchanged.

This is the DIN-SQL gentle self-correction module. Do not assume the SQL is wrong. Carefully check table names, column names, joins, aggregation, GROUP BY, HAVING, ORDER BY, DISTINCT, DESC, LIMIT, time filters, entity filters, and PostgreSQL syntax. Correct minor mistakes only when needed.

Current date: {current_time}

Database schema and Foreign keys:
{schema_context}

Question:
{question}

SQL:
```sql
{sql_query}
```

Return only valid JSON with this shape:
{
  "reasoning": "Potential issues checked and whether the SQL was changed.",
  "sql": "SELECT ..."
}
