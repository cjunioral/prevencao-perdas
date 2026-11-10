-- =============================================================================
-- 02_indice_regional.sql
-- Pergunta: qual o índice de cada regional e da rede, por categoria?
--
-- Lógica:
--   * índice agregado = SOMA das perdas / SOMA das vendas (razão das somas).
--     NUNCA a média dos índices das lojas: uma loja pequena com índice alto
--     pesaria igual a uma loja grande. A razão das somas pondera pela venda;
--   * GROUPING SETS calcula, numa única passada, regional x categoria x mês e
--     rede x categoria x mês, além do período inteiro (set+out);
--   * lojas sem regional cadastrada aparecem como "SEM REGIONAL" (não somem).
-- =============================================================================
WITH m AS (
    SELECT * FROM analitico.vw_indice_perda_mensal
    WHERE mes BETWEEN DATE '2026-09-01' AND DATE '2026-10-01'
)
SELECT CASE WHEN GROUPING(nome_regional) = 1 THEN 'REDE' ELSE nome_regional END   AS nivel,
       categoria,
       CASE WHEN GROUPING(ano_mes) = 1 THEN 'set+out' ELSE ano_mes END           AS periodo,
       SUM(venda_liquida)                                                       AS venda_liquida,
       SUM(avaria_identificada)                                                 AS avaria_identificada,
       SUM(perda_nao_identificada)                                              AS perda_nao_identificada,
       SUM(perda_total)                                                         AS perda_total,
       ROUND(100 * SUM(perda_total) / NULLIF(SUM(venda_liquida), 0), 2)         AS indice_pct
FROM m
GROUP BY GROUPING SETS (
    (nome_regional, categoria, ano_mes),
    (nome_regional, categoria),
    (categoria, ano_mes),
    (categoria)
)
ORDER BY GROUPING(nome_regional), nivel, categoria, periodo;
