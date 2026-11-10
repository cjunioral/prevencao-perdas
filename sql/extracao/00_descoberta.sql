-- =============================================================================
-- 00_descoberta.sql — rodar ANTES de tudo, no SQL Developer/DBeaver, na Consinco
-- Objetivo: confirmar nomes de tabelas/colunas e descobrir parâmetros (regional,
-- categorias, CGOs, tipos de local). Só lê o DICIONÁRIO de dados e cadastros
-- pequenos: custo desprezível para a produção.
-- Anote os resultados no README (seção "Decisões e suposições").
-- =============================================================================

-- 1) Onde está a regional? Procure tabelas e colunas com REGIONAL no nome.
SELECT owner, table_name FROM all_tables
 WHERE table_name LIKE '%REGIONAL%' ORDER BY 1, 2;

SELECT owner, table_name, column_name, data_type
  FROM all_tab_columns
 WHERE column_name LIKE '%REGIONAL%'
   AND table_name IN ('MAX_EMPRESA', 'GE_EMPRESA', 'MAX_DIVISAO')
 ORDER BY table_name, column_name;
-- Depois confira: SELECT nroempresa, nomereduzido, <coluna_regional> FROM max_empresa;

-- 2) Colunas das tabelas usadas nas extrações (confirme os nomes usados em 01..05)
SELECT table_name, column_id, column_name, data_type, nullable
  FROM all_tab_columns
 WHERE table_name IN ('MRL_LANCTOESTOQUE', 'MAX_CODGERALOPER', 'MRL_LOCAL',
                      'MAP_PRODUTO', 'MAP_FAMDIVCATEG', 'MAP_CATEGORIA',
                      'MAX_EMPRESA', 'MAP_PRODCODIGO', 'MAXV_ABCDISTRIBBASE')
 ORDER BY table_name, column_id;

-- 3) Qual coluna do CGO indica "entra no ABC de movimentação"?
SELECT column_name, data_type FROM all_tab_columns
 WHERE table_name = 'MAX_CODGERALOPER'
   AND (column_name LIKE '%ABC%' OR column_name LIKE '%MOVTO%')
 ORDER BY column_name;

-- 4) CGOs candidatos a avaria (confirme com a área quais são de avaria)
SELECT g.codgeraloper, g.descricao, g.tipcgo
  FROM max_codgeraloper g
 WHERE UPPER(g.descricao) LIKE '%AVARIA%' OR UPPER(g.descricao) LIKE '%QUEBRA%'
    OR UPPER(g.descricao) LIKE '%PERDA%'  OR g.codgeraloper IN (403, 552)
 ORDER BY g.codgeraloper;

-- 5) Tipos de local de estoque (confirmar o significado de 'T' e 'L')
SELECT tiplocal, COUNT(*) AS qtd FROM mrl_local GROUP BY tiplocal ORDER BY 1;

-- 6) Categorias Açougue e Hortifruti: SEQCATEGORIA, nível e divisão
--    -> preencha CATEGORIAS_ESCOPO e NIVEL_CATEGORIA no .env
SELECT c.nrodivisao, c.seqcategoria, c.categoria, c.nivelhierarquia, c.seqcategoriapai
  FROM map_categoria c
 WHERE UPPER(TRANSLATE(c.categoria, 'ÇçÃãÁá', 'CcAaAa')) LIKE '%ACOUGUE%'
    OR UPPER(c.categoria) LIKE '%HORTI%' OR UPPER(c.categoria) LIKE '%FLV%'
 ORDER BY c.nrodivisao, c.nivelhierarquia;

-- 7) Teste de unicidade: alguma família tem MAIS DE UMA ligação ativa no
--    mesmo nível? Se sim, o JOIN duplicaria avarias/vendas -> tratar antes.
SELECT fc.seqfamilia, fc.nrodivisao, COUNT(*) AS ligacoes_ativas
  FROM map_famdivcateg fc
  JOIN map_categoria c ON c.seqcategoria = fc.seqcategoria AND c.nrodivisao = fc.nrodivisao
 WHERE fc.status = 'A' AND c.nivelhierarquia = 1      -- use o seu NIVEL_CATEGORIA
 GROUP BY fc.seqfamilia, fc.nrodivisao
HAVING COUNT(*) > 1;

-- 8) Índices das tabelas grandes: confirme que a coluna de data usada no filtro
--    é indexada (senão a consulta faz full scan na produção).
SELECT table_name, index_name, column_name, column_position
  FROM all_ind_columns
 WHERE table_name IN ('MRL_LANCTOESTOQUE')
 ORDER BY index_name, column_position;

-- 9) Capturar o SQL real do relatório "ABC de Venda Sintético" (precisa de
--    permissão em V$SQL; peça ao DBA se não tiver). Rode o relatório na tela e,
--    logo depois:
-- SELECT sql_id, module, last_active_time, sql_fulltext
--   FROM v$sql
--  WHERE last_active_time > SYSDATE - 10/1440
--    AND UPPER(sql_fulltext) LIKE '%ABC%'
--  ORDER BY last_active_time DESC;
