For the given question, database schema, and BUGGY SQL, identify and correct errors in the BUGGY SQL.

This is the DIN-SQL generic self-correction module. Correct only the SQL. Check table names, column names, joins, aggregation, GROUP BY, HAVING, ORDER BY, DISTINCT, DESC, LIMIT, time filters, entity filters, and PostgreSQL syntax.

Current date: {current_time}

Database schema and Foreign keys:
{schema_context}

Question:
{question}

BUGGY SQL:
```sql
{sql_query}
```

Return only valid JSON with this shape:
{
  "reasoning": "Potential issues checked and corrections made.",
  "sql": "SELECT ..."
}
