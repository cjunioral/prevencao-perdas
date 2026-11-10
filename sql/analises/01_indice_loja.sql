-- =============================================================================
-- 01_indice_loja.sql
-- Pergunta: qual o índice de perda de cada loja, por categoria e por mês, e
-- quanto variou de setembro para outubro (em pontos percentuais)?
--
-- Lógica:
--   * a view vw_indice_perda_mensal já está no grão loja x categoria x mês,
--     com índice = (avaria identificada + perda não identificada) / venda líquida
--     da categoria na loja no mês;
--   * pivotamos setembro e outubro lado a lado (FILTER) para calcular a variação;
--   * variação em p.p. = índice_out(%) - índice_set(%). Ex.: 2,10% -> 2,85% = +0,75 p.p.
--     (não é variação percentual: 0,75 p.p. seria +35,7% em termos relativos);
--   * índice nulo = sem venda da categoria na loja no mês (divisão por zero
--     evitada com NULLIF na view); variação nula se faltar um dos meses.
-- Ordenado pela maior piora: as primeiras linhas são onde agir.
-- =============================================================================
WITH m AS (
    SELECT * FROM analitico.vw_indice_perda_mensal
    WHERE mes IN (DATE '2026-09-01', DATE '2026-10-01')
)
SELECT nro_empresa,
       nome_loja,
       nome_regional,
       categoria,
       SUM(venda_liquida) FILTER (WHERE mes = '2026-09-01')            AS venda_set,
       SUM(perda_total)   FILTER (WHERE mes = '2026-09-01')            AS perda_set,
       ROUND(100 * MAX(indice_perda) FILTER (WHERE mes = '2026-09-01'), 2) AS indice_set_pct,
       SUM(venda_liquida) FILTER (WHERE mes = '2026-10-01')            AS venda_out,
       SUM(perda_total)   FILTER (WHERE mes = '2026-10-01')            AS perda_out,
       ROUND(100 * MAX(indice_perda) FILTER (WHERE mes = '2026-10-01'), 2) AS indice_out_pct,
       ROUND(100 * (MAX(indice_perda) FILTER (WHERE mes = '2026-10-01')
                  - MAX(indice_perda) FILTER (WHERE mes = '2026-09-01')), 2) AS variacao_pp
FROM m
GROUP BY nro_empresa, nome_loja, nome_regional, categoria
ORDER BY variacao_pp DESC NULLS LAST, nro_empresa, categoria;
