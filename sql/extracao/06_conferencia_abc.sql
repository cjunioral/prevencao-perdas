-- =============================================================================
-- 06_conferencia_abc.sql — conferência da venda líquida com a tela
-- Rode no Oracle (SQL Developer) com o mesmo período/loja/categoria que você
-- usar no relatório "ABC de Venda Sintético". Compare linha a linha e cole o
-- resultado no README. Faça para pelo menos 2 lojas x 2 categorias x 2 meses.
--
-- O lado do banco analítico está em sql/analises/00_conferencia_venda.sql
-- (os três números — tela, Oracle e PostgreSQL — devem ser iguais).
-- =============================================================================
SELECT nro_empresa, seq_categoria, TO_CHAR(dta_venda, 'YYYY-MM') AS mes,
       SUM(vlr_venda_bruta)   AS venda_bruta,
       SUM(vlr_devolucao)     AS devolucao,
       SUM(vlr_venda_liquida) AS venda_liquida
  FROM ( /* cole aqui o SELECT de 05_vendas.sql */
         SELECT v.nroempresa AS nro_empresa, c.seqcategoria AS seq_categoria,
                TRUNC(v.dtavda) AS dta_venda,
                SUM(NVL(v.vlritem, 0)) AS vlr_venda_bruta,
                SUM(NVL(v.vlrdevolitem, 0)) AS vlr_devolucao,
                SUM(NVL(v.vlritem, 0)) - SUM(NVL(v.vlrdevolitem, 0)) AS vlr_venda_liquida
           FROM maxv_abcdistribbase v
           JOIN max_empresa e      ON e.nroempresa = v.nroempresa
           JOIN map_produto p      ON p.seqproduto = v.seqproduto
           JOIN map_famdivcateg fc ON fc.seqfamilia = p.seqfamilia AND fc.nrodivisao = e.nrodivisao AND fc.status = 'A'
           JOIN map_categoria c    ON c.seqcategoria = fc.seqcategoria AND c.nrodivisao = fc.nrodivisao AND c.nivelhierarquia = :nivel_categoria
          WHERE v.dtavda >= DATE '2026-09-01' AND v.dtavda < DATE '2026-11-01'
            AND v.nroempresa IN (:loja1, :loja2)
            AND c.seqcategoria IN (:cat_acougue, :cat_hortifruti)
          GROUP BY v.nroempresa, c.seqcategoria, TRUNC(v.dtavda) )
 GROUP BY nro_empresa, seq_categoria, TO_CHAR(dta_venda, 'YYYY-MM')
 ORDER BY 1, 2, 3;
