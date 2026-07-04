DIN-SQL finance-domain few-shot examples.

Schema linking example:
Q: "Doanh thu của Công ty Cổ phần Tập đoàn Công nghệ CMC trong quý 3 năm 2024 là bao nhiêu tỷ VND? [entity]"
A: Let's think step by step. In the question, "Doanh thu" maps to the income-statement metric stored in fact_financial_statement.category_code and dim_financial_statement_category.category_name. "Công ty Cổ phần Tập đoàn Công nghệ CMC" maps to dim_company.company_name and the stock code CMG. "quý 3 năm 2024" maps to fact_financial_statement.year and fact_financial_statement.quarter. We need the foreign key fact_financial_statement.stock_code = dim_company.stock_code and fact_financial_statement.category_code = dim_financial_statement_category.category_code.
Schema_links: [fact_financial_statement.data,fact_financial_statement.stock_code = dim_company.stock_code,fact_financial_statement.category_code = dim_financial_statement_category.category_code,dim_company.company_name,dim_company.stock_code,dim_financial_statement_category.category_name,CMG,doanh thu,2024,3]

Classification and decomposition example:
Q: "Doanh thu của Công ty Cổ phần Tập đoàn Công nghệ CMC trong quý 3 năm 2024 là bao nhiêu tỷ VND? [entity]"
schema_links: [fact_financial_statement.data,fact_financial_statement.stock_code = dim_company.stock_code,fact_financial_statement.category_code = dim_financial_statement_category.category_code,dim_company.stock_code,dim_financial_statement_category.category_name,CMG,doanh thu,2024,3]
A: Let's think step by step. The SQL query needs these tables = [fact_financial_statement]. If the known stock code and category code are used directly, we do not need JOIN. It does not require nested queries with INTERSECT, UNION, EXCEPT, IN, NOT IN, EXISTS, or aggregate subqueries, and the answer to the sub-questions = [""].
Label: "EASY"

Easy SQL generation example:
Q: "Doanh thu của Công ty Cổ phần Tập đoàn Công nghệ CMC trong quý 3 năm 2024 là bao nhiêu tỷ VND? [entity]"
Schema_links: [fact_financial_statement.data,fact_financial_statement.stock_code,CMG,fact_financial_statement.category_code,IS_001,fact_financial_statement.year,2024,fact_financial_statement.quarter,3]
SQL: SELECT data FROM fact_financial_statement WHERE stock_code = 'CMG' AND category_code = 'IS_001' AND year = 2024 AND quarter = 3

Non-nested SQL generation example:
Q: "Liệt kê top 10 công ty ngành Construction and Materials theo lợi nhuận sau thuế trong quý 4 năm 2025. [tuple]"
Schema_links: [dim_company.stock_code,dim_company.industry_id = dim_industry.industry_id,dim_industry.industry_name,Construction and Materials,fact_financial_statement.stock_code = dim_company.stock_code,fact_financial_statement.category_code,net_income,fact_financial_statement.year,2025,fact_financial_statement.quarter,4,fact_financial_statement.data]
A: Let's think step by step. For creating the SQL for the given question, we need to join these tables = [fact_financial_statement,dim_company,dim_industry].
First, create an intermediate representation, then use it to construct the SQL query.
Intermediate_representation: select dim_company.stock_code , fact_financial_statement.data from fact_financial_statement where dim_industry.industry_name = "Construction and Materials" and fact_financial_statement.category_code = net_income and year = 2025 and quarter = 4 order by fact_financial_statement.data desc limit 10
SQL: SELECT c.stock_code, fs.data AS net_income FROM fact_financial_statement AS fs JOIN dim_company AS c ON fs.stock_code = c.stock_code JOIN dim_industry AS i ON c.industry_id = i.industry_id WHERE i.industry_name = 'Construction and Materials' AND fs.category_code = 'IS_015' AND fs.year = 2025 AND fs.quarter = 4 ORDER BY fs.data DESC LIMIT 10

Nested SQL generation example:
Q: "Trong quý 3 năm 2024, chênh lệch sinh lời giữa cổ phiếu BSR và VNINDEX là bao nhiêu điểm phần trăm? [entity]"
Schema_links: [fact_stock_daily.stock_code,BSR,fact_stock_daily.time,2024-Q3,fact_stock_daily.close,fact_index_daily.index_id = dim_market_index.index_id,dim_market_index.index_name,VNINDEX,fact_index_daily.time,fact_index_daily.close]
A: Let's think step by step. The question can be solved by knowing the answer to the following sub-questions: "What are the first and last close prices for BSR in 2024-Q3?" and "What are the first and last close prices for VNINDEX in 2024-Q3?".
The SQL query for the sub-question "What are the first and last close prices for BSR in 2024-Q3?" computes the first and last close from fact_stock_daily.
The SQL query for the sub-question "What are the first and last close prices for VNINDEX in 2024-Q3?" computes the first and last close from fact_index_daily joined through dim_market_index.
Intermediate_representation: select stock_return - index_return where stock_return = (last_close - first_close) / first_close * 100 and index_return = (last_close - first_close) / first_close * 100
SQL: WITH stock_prices AS (SELECT (SELECT close FROM fact_stock_daily WHERE stock_code = 'BSR' AND time >= DATE '2024-07-01' AND time <= DATE '2024-09-30' ORDER BY time ASC LIMIT 1) AS first_close, (SELECT close FROM fact_stock_daily WHERE stock_code = 'BSR' AND time >= DATE '2024-07-01' AND time <= DATE '2024-09-30' ORDER BY time DESC LIMIT 1) AS last_close), index_prices AS (SELECT (SELECT close FROM fact_index_daily WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time >= DATE '2024-07-01' AND time <= DATE '2024-09-30' ORDER BY time ASC LIMIT 1) AS first_close, (SELECT close FROM fact_index_daily WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time >= DATE '2024-07-01' AND time <= DATE '2024-09-30' ORDER BY time DESC LIMIT 1) AS last_close), returns AS (SELECT ((s.last_close - s.first_close) / s.first_close) * 100 AS stock_return, ((i.last_close - i.first_close) / i.first_close) * 100 AS index_return FROM stock_prices AS s, index_prices AS i) SELECT stock_return - index_return AS diff_percentage_point FROM returns
