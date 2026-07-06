# Use the schema links and Intermediate_representation to generate the PostgreSQL query for the question.

This is the DIN-SQL SQL generation module for the NON-NESTED class. Follow the paper's order:
1. Think step by step.
2. State the tables that must be joined.
3. Create an Intermediate_representation in NatSQL-like form.
4. Convert that intermediate representation into executable PostgreSQL.

Current date: {current_time}

Database schema and Foreign keys:
{schema_context}

Few-shot examples:
{examples_text}

Q: "{question}"
Schema_links: {schema_links}
Join tables: {join_tables}

Return only valid JSON with this shape:
{
  "reasoning": "Let's think step by step. For creating the SQL for the given question, we need to join these tables = [...]. First, create an intermediate representation, then use it to construct the SQL query.",
  "intermediate_representation": "select ...",
  "sql": "SELECT ..."
}
