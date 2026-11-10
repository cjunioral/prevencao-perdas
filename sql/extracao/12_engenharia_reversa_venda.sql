-- =============================================================================
-- 12_engenharia_reversa_venda.sql — descobrir a fórmula da venda líquida do
-- "ABC de Venda Sintético" comparando com a tela (10/11/2026)
--
-- Contexto: o código da procedure não é acessível ao usuário de leitura
-- (ALL_SOURCE vazio) e o resultado da tela fica numa tabela temporária de sessão
-- (MBIX_TABCSINTETICA, SYS$SESSION). Por isso: calcular as fórmulas candidatas
-- na view base e ver qual bate com o total da tela, para a MESMA loja e o MESMO dia.
--
-- Recorte: loja 10, 08/11/2026 (o mesmo da consulta 743190 do SQL Monitor).
-- Leve: 1 loja x 1 dia, filtro de data sem função na coluna.
-- =============================================================================

-- A) Fórmulas candidatas, todas as categorias (comparar com a linha TOTAL da tela)
SELECT COUNT(*)                                                     AS linhas,
       COUNT(DISTINCT v.seqproduto)                                 AS produtos,
       ROUND(SUM(NVL(v.vlritem, 0)), 2)                             AS a_vlritem,
       ROUND(SUM(NVL(v.vlrdevolitem, 0)), 2)                        AS b_devolucao,
       ROUND(SUM(NVL(v.vlritem, 0) - NVL(v.vlrdevolitem, 0)), 2)    AS c_item_menos_devol,
       ROUND(SUM(NVL(v.vlrdesconto, 0)), 2)                         AS d_desconto,
       ROUND(SUM(NVL(v.vlricmsst, 0) - NVL(v.vlrdevolicmsst, 0)), 2)          AS e_icmsst_liq,
       ROUND(SUM(NVL(v.vlritemsemst, 0) - NVL(v.vlrdevolitemsemst, 0)), 2)    AS f_semst_liq,
       ROUND(SUM(NVL(v.vlrdescforanf, 0)), 2)                       AS g_desc_fora_nf,
       ROUND(SUM(NVL(v.vlracrescimo, 0)), 2)                        AS h_acrescimo,
       ROUND(SUM(NVL(v.qtditem, 0) - NVL(v.qtddevolitem, 0)), 3)    AS q_qtd_liquida
  FROM maxv_abcdistribbase v
 WHERE v.nroempresa = 10
   AND v.dtavda >= DATE '2026-11-08'
   AND v.dtavda <  DATE '2026-11-09';

-- B) Quebra por tipo de operação: mostra se há transferências/outras operações
--    que o relatório exclui (parâmetro "desconsidera transferências = S")
SELECT v.acmcompravenda, v.tipcgo, v.codgeraloper, g.descricao,
       COUNT(*) AS linhas,
       ROUND(SUM(NVL(v.vlritem, 0)), 2)      AS vlritem,
       ROUND(SUM(NVL(v.vlrdevolitem, 0)), 2) AS devolucao
  FROM maxv_abcdistribbase v
  LEFT JOIN max_codgeraloper g ON g.codgeraloper = v.codgeraloper
 WHERE v.nroempresa = 10
   AND v.dtavda >= DATE '2026-11-08'
   AND v.dtavda <  DATE '2026-11-09'
 GROUP BY v.acmcompravenda, v.tipcgo, v.codgeraloper, g.descricao
 ORDER BY vlritem DESC;

-- C) Mesmas fórmulas só para Açougue e Hortifruti (2ª conferência, por categoria)
SELECT c.categoria,
       ROUND(SUM(NVL(v.vlritem, 0)), 2)                             AS a_vlritem,
       ROUND(SUM(NVL(v.vlrdevolitem, 0)), 2)                        AS b_devolucao,
       ROUND(SUM(NVL(v.vlritem, 0) - NVL(v.vlrdevolitem, 0)), 2)    AS c_item_menos_devol,
       ROUND(SUM(NVL(v.vlritemsemst, 0) - NVL(v.vlrdevolitemsemst, 0)), 2) AS f_semst_liq
  FROM maxv_abcdistribbase v
  JOIN map_produto p      ON p.seqproduto   = v.seqproduto
  JOIN map_famdivcateg fc ON fc.seqfamilia  = p.seqfamilia AND fc.nrodivisao = 1 AND fc.status = 'A'
  JOIN map_categoria c    ON c.seqcategoria = fc.seqcategoria AND c.nrodivisao = 1
                         AND c.nivelhierarquia = 1 AND c.tipcategoria = 'M'
 WHERE v.nroempresa = 10
   AND v.dtavda >= DATE '2026-11-08'
   AND v.dtavda <  DATE '2026-11-09'
   AND c.seqcategoria IN (11, 24)
 GROUP BY c.categoria;
