news


```
CREATE SEARCH INDEX idx_articles_search
ON `neusolution.ktln.news`
(title, text);
```


```
CREATE SEARCH INDEX idx_fs_search
ON `neusolution.ktln.financial_statement_dim`
category_name;
```

```
CREATE SEARCH INDEX idx_fr_search
ON `neusolution.ktln.financial_ratio_dim`
(ratio_name, ratio_code);
```

```
SELECT
  url,
  title,
  source,
  pub_date
FROM `project.dataset.articles`
WHERE SEARCH(title, text, 'interest rate hike');
```