-- =============================================================================
-- 03_perda_identificada_vs_nao.sql
-- Pergunta: em cada loja, quanto da perda total é identificada e quanto não é?
-- Quais lojas têm mais de 70% de perda não identificada?
--
-- Lógica:
--   * período inteiro (set+out), as duas categorias somadas: a pergunta é por loja;
--   * só loja x categoria x mês com inventário: sem ele, a perda não identificada
--     é desconhecida e o % "identificado" sairia 100% por falta de dado;
--   * % não identificada = perda não identificada / perda total;
--   * perda não identificada alta indica que a loja perde sem registrar
--     (furto, erro de recebimento, quebra não lançada): é processo, não só produto;
--   * a coluna acima_70 responde a segunda pergunta; para ver só essas lojas,
--     descomente o filtro no fim.
-- Detalhe por categoria: troque "GROUP BY nro_empresa, nome_loja, nome_regional"
-- por "... , categoria" e adicione categoria no SELECT.
-- =============================================================================
WITH loja AS (
    SELECT nro_empresa, nome_loja, nome_regional,
           SUM(avaria_identificada)    AS perda_identificada,
           SUM(perda_nao_identificada) AS perda_nao_identificada,
           SUM(perda_total)            AS perda_total,
           SUM(venda_liquida)          AS venda_liquida
    FROM analitico.vw_indice_perda_mensal
    WHERE mes BETWEEN DATE '2026-09-01' AND DATE '2026-10-01'
      AND com_inventario
    GROUP BY nro_empresa, nome_loja, nome_regional
)
SELECT nro_empresa,
       nome_loja,
       nome_regional,
       perda_identificada,
       perda_nao_identificada,
       perda_total,
       ROUND(100 * perda_identificada     / NULLIF(perda_total, 0), 1) AS pct_identificada,
       ROUND(100 * perda_nao_identificada / NULLIF(perda_total, 0), 1) AS pct_nao_identificada,
       ROUND(100 * perda_total / NULLIF(venda_liquida, 0), 2)          AS indice_pct,
       perda_nao_identificada / NULLIF(perda_total, 0) > 0.70          AS acima_70
FROM loja
-- WHERE perda_nao_identificada / NULLIF(perda_total, 0) > 0.70
ORDER BY pct_nao_identificada DESC NULLS LAST;
