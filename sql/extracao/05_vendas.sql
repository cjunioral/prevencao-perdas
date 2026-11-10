-- =============================================================================
-- 05_vendas.sql — venda líquida por loja x categoria x dia
-- Contrato: nro_empresa, seq_categoria, dta_venda, vlr_venda_bruta,
--           vlr_devolucao, vlr_venda_liquida
--
-- Lógica copiada do SQL do próprio relatório "Análise ABC Venda Distribuição
-- Sintética" (botão SQL da tela, consulta 744454, 10/11/2026):
--   * base: MADMV_ABCDISTRIBPROD (não a MAXV_ABCDISTRIBBASE);
--   * data: DTAENTRADASAIDA;
--   * só operações que acumulam venda:
--       DECODE(TIPTABELA, 'S', CGOACMCOMPRAVENDA, ACMCOMPRAVENDA) IN ('S', 'I');
--   * só produtos com embalagem unitária cadastrada (MAP_FAMEMBALAGEM, QTDEMBALAGEM = 1);
--   * todos os segmentos (a tela usa os 13): sem filtro de segmento aqui;
--   * VENDA LÍQUIDA = SUM(VLRITEM - VLRDEVOLITEM) — exatamente a coluna
--     VLRVENDALIQ do relatório ("Valor Total Liq" na tela). Sem dedução de impostos.
--
-- CONFERÊNCIA (loja 10, 08/11/2026, todas as categorias):
--   tela "Valor Total Liq" = R$ 352.775,08 | esta lógica = R$ 352.775,08 | dif. R$ 0,00
--   4.725 produtos e quantidade 52.392,436 iguais nos dois lados.
--
-- Categoria: família -> categoria nível 1 da árvore Mix (TIPCATEGORIA = 'M'),
-- ligação ativa, na divisão do lançamento. Só Açougue e Hortifruti.
-- =============================================================================
SELECT a3.nroempresa                                         AS nro_empresa,
       c.seqcategoria                                        AS seq_categoria,
       TRUNC(a3.dtaentradasaida)                             AS dta_venda,
       SUM(NVL(a3.vlritem, 0))                               AS vlr_venda_bruta,
       SUM(NVL(a3.vlrdevolitem, 0))                          AS vlr_devolucao,
       SUM(NVL(a3.vlritem, 0) - NVL(a3.vlrdevolitem, 0))     AS vlr_venda_liquida
  FROM madmv_abcdistribprod a3
  JOIN map_produto a      ON a.seqproduto   = a3.seqproduto
  JOIN map_famembalagem k ON k.seqfamilia   = a.seqfamilia
                         AND k.qtdembalagem = 1
  JOIN map_famdivcateg fc ON fc.seqfamilia  = a.seqfamilia
                         AND fc.nrodivisao  = a3.nrodivisao
                         AND fc.status      = 'A'
  JOIN map_categoria c    ON c.seqcategoria = fc.seqcategoria
                         AND c.nrodivisao   = fc.nrodivisao
                         AND c.nivelhierarquia = :nivel_categoria
                         AND c.tipcategoria = 'M'                  -- árvore Mix (há 3 árvores)
 WHERE a3.dtaentradasaida >= :dt_ini
   AND a3.dtaentradasaida <  :dt_fim
   AND DECODE(a3.tiptabela, 'S', a3.cgoacmcompravenda, a3.acmcompravenda) IN ('S', 'I')
   AND c.seqcategoria IN (:categorias)
 GROUP BY a3.nroempresa, c.seqcategoria, TRUNC(a3.dtaentradasaida)
