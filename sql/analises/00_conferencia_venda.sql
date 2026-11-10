-- =============================================================================
-- 00_conferencia_venda.sql — lado PostgreSQL da conferência com o ABC de Venda
-- Mesmo recorte de sql/extracao/06_conferencia_abc.sql (Oracle) e da tela.
-- Os três números (tela, Oracle, PostgreSQL) precisam ser iguais.
-- =============================================================================
SELECT v.nro_empresa,
       l.nome_loja,
       c.categoria,
       to_char(v.data, 'YYYY-MM')     AS mes,
       SUM(v.vlr_venda_bruta)         AS venda_bruta,
       SUM(v.vlr_devolucao)           AS devolucao,
       SUM(v.vlr_venda_liquida)       AS venda_liquida
FROM analitico.fato_venda v
JOIN analitico.dim_loja l      ON l.nro_empresa   = v.nro_empresa
JOIN analitico.dim_categoria c ON c.seq_categoria = v.seq_categoria
WHERE v.data BETWEEN DATE '2026-09-01' AND DATE '2026-10-31'
  -- AND v.nro_empresa IN (1, 2)      -- mesmas lojas escolhidas na tela
GROUP BY v.nro_empresa, l.nome_loja, c.categoria, to_char(v.data, 'YYYY-MM')
ORDER BY 1, 3, 4;
