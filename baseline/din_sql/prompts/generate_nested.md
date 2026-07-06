# Use the intermediate representation and the schema links to generate the PostgreSQL query for the question.

This is the DIN-SQL SQL generation module for the NESTED class. Follow the paper's order:
1. Think step by step.
2. Solve each detected sub-question by writing its SQL query.
3. Use the sub-question SQLs to construct an Intermediate_representation.
4. Convert the intermediate representation into the final executable PostgreSQL query.

Current date: {current_time}

Database schema and Foreign keys:
{schema_context}

Few-shot examples:
{examples_text}

Q: "{question}"
Schema_links: {schema_links}
Sub-questions: {sub_questions}
Join tables: {join_tables}

Return only valid JSON with this shape:
{
  "reasoning": "Let's think step by step. The question can be solved by knowing the answer to the following sub-question(s) ...",
  "subquery_sqls": {
    "sub-question text": "SELECT ..."
  },
  "intermediate_representation": "select ...",
  "sql": "SELECT ..."
}
