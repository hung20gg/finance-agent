Prepare training and testing data for LLM


Style: GRPO ready and Huggingface format. Including
- Question (prompt)
- Ground Truth (label)


The data will be randomly selected from the datasource.

E.g: at 09/2025, sample:
 - % Return of a stock/stock index within that quarter
 - % Increase of Gold price within that quarter
 - Revenue, EBITDA, Net Income of a company within that quarter
 - NIM, Bad debt ratio of a bank within that quarter
 - % Increase of Inflation within that quarter
 - % Increase of Unemployment within that quarter


 The training data will be ranged from Q3 2023 -> Q2 2025
 The testing data will be Q3 2025