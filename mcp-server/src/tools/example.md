## Doanh thu của Công ty Cổ phần Thực phẩm Sao Ta trong quý 1 năm 2025 so với quý 4 năm 2024 chênh lệch bao nhiêu tỷ VND?

```sql
SELECT 
   (SELECT data FROM financial_statement WHERE stock_code='FMC' AND category_code='IS_020' AND year=2025 AND quarter=1 ORDER BY date_added DESC LIMIT 1) -
   (SELECT data FROM financial_statement WHERE stock_code='FMC' AND category_code='IS_020' AND year=2024 AND quarter=4 ORDER BY date_added DESC LIMIT 1) 
   AS diff_billion_vnd;
```