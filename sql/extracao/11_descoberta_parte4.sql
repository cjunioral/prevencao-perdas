-- =============================================================================
-- 11_descoberta_parte4.sql — quarta rodada (10/11/2026). Leve: cadastros e dicionário.
-- =============================================================================

-- A) A família tem 3 ligações ativas no nível 1 porque MAP_CATEGORIA tem mais de
--    uma árvore (TIPCATEGORIA). Confirmar: com 'M' (mercadológica) deve vir VAZIO.
SELECT c.tipcategoria, COUNT(DISTINCT c.seqcategoria) AS categorias_nivel1
  FROM map_categoria c WHERE c.nivelhierarquia = 1 GROUP BY c.tipcategoria;

SELECT fc.seqfamilia, COUNT(*) AS ligacoes_ativas
  FROM map_famdivcateg fc
  JOIN map_categoria c ON c.seqcategoria = fc.seqcategoria AND c.nrodivisao = fc.nrodivisao
 WHERE fc.status = 'A' AND c.nivelhierarquia = 1 AND c.tipcategoria = 'M'
 GROUP BY fc.seqfamilia
HAVING COUNT(*) > 1;

-- B) CGO 563 (classificado como avaria 'AS' no ABC de movimentação)
SELECT codgeraloper, descricao, tipcgo, tipuso, status, indfixoabcmovimentacao, indtipocgomovto
  FROM max_codgeraloper WHERE codgeraloper IN (549, 552, 562, 563, 403);

-- C) REGIONAL: candidatos
SELECT 'CT_REGIONAIS' AS tabela, COUNT(*) AS linhas FROM ct_regionais
UNION ALL SELECT 'CT_REGIONAISEMPRESAS', COUNT(*) FROM ct_regionaisempresas
UNION ALL SELECT 'MSUV_EMPRESASREGIAO', COUNT(*) FROM msuv_empresasregiao
UNION ALL SELECT 'MAX_REGVDAEMP', COUNT(*) FROM max_regvdaemp;

SELECT * FROM ct_regionais;
SELECT * FROM ct_regionaisempresas;
SELECT * FROM msuv_empresasregiao;   -- região de compra x empresa
SELECT * FROM max_regvda;            -- regiões de venda
SELECT * FROM max_regvdaemp;         -- região de venda x empresa
