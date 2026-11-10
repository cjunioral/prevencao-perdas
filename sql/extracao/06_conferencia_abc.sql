-- =============================================================================
-- 06_conferencia_abc.sql — conferência da venda líquida com a tela do ABC
-- Mesma lógica de 05_vendas.sql, com loja e período fixos. Compare com a coluna
-- "Valor Total Liq" da tela "Análise ABC Venda Distribuição Sintética"
-- (mesmo período, mesma loja, Detalhe 1 = Categoria para ver por categoria).
--
-- A) TOTAL da loja (todas as categorias) -> compara com a linha TOTAL da tela
-- B) por categoria (Açougue e Hortifruti) -> compara com Detalhe 1 = Categoria
-- =============================================================================

-- A) total da loja, sem filtro de categoria
SELECT a3.nroempresa,
       COUNT(DISTINCT a3.seqproduto)                         AS produtos,
       ROUND(SUM(a3.qtditem - a3.qtddevolitem), 3)           AS quantidade,
       ROUND(SUM(NVL(a3.vlritem, 0) - NVL(a3.vlrdevolitem, 0)), 2) AS venda_liquida
  FROM madmv_abcdistribprod a3
  JOIN map_produto a      ON a.seqproduto   = a3.seqproduto
  JOIN map_famembalagem k ON k.seqfamilia   = a.seqfamilia AND k.qtdembalagem = 1
 WHERE a3.nroempresa = :loja
   AND a3.dtaentradasaida >= :dt_ini
   AND a3.dtaentradasaida <  :dt_fim
   AND DECODE(a3.tiptabela, 'S', a3.cgoacmcompravenda, a3.acmcompravenda) IN ('S', 'I')
 GROUP BY a3.nroempresa;

-- B) por categoria
SELECT a3.nroempresa, c.seqcategoria, c.categoria,
       ROUND(SUM(NVL(a3.vlritem, 0) - NVL(a3.vlrdevolitem, 0)), 2) AS venda_liquida
  FROM madmv_abcdistribprod a3
  JOIN map_produto a      ON a.seqproduto   = a3.seqproduto
  JOIN map_famembalagem k ON k.seqfamilia   = a.seqfamilia AND k.qtdembalagem = 1
  JOIN map_famdivcateg fc ON fc.seqfamilia  = a.seqfamilia AND fc.nrodivisao = a3.nrodivisao
                         AND fc.status = 'A'
  JOIN map_categoria c    ON c.seqcategoria = fc.seqcategoria AND c.nrodivisao = fc.nrodivisao
                         AND c.nivelhierarquia = 1 AND c.tipcategoria = 'M'
 WHERE a3.nroempresa = :loja
   AND a3.dtaentradasaida >= :dt_ini
   AND a3.dtaentradasaida <  :dt_fim
   AND DECODE(a3.tiptabela, 'S', a3.cgoacmcompravenda, a3.acmcompravenda) IN ('S', 'I')
   AND c.seqcategoria IN (11, 24)
 GROUP BY a3.nroempresa, c.seqcategoria, c.categoria
 ORDER BY 2;
