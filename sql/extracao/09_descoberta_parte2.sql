-- =============================================================================
-- 09_descoberta_parte2.sql — segunda rodada de descoberta (10/11/2026)
-- Fecha os pontos que a 1ª rodada (00_descoberta.sql) deixou em aberto.
-- Só dicionário de dados e cadastros pequenos: leve, pode rodar em horário comercial.
-- Rodar com Alt+X (DBeaver) e mandar o resultado de cada aba.
-- =============================================================================

-- A) REGIONAL: a regional não está em MAX_EMPRESA; está em tabelas customizadas.
--    A1) colunas das duas tabelas
SELECT table_name, column_id, column_name, data_type, nullable
  FROM all_tab_columns
 WHERE table_name IN ('CT_REGIONAIS', 'CT_REGIONAISEMPRESAS')
 ORDER BY table_name, column_id;

--    A2) conteúdo (cadastros pequenos)
SELECT * FROM ct_regionais;
SELECT * FROM ct_regionaisempresas;

-- B) CGOs DE AVARIA: o que diferencia os CGOs de avaria e os do ABC de movimentação?
--    B1) as flags candidatas para os CGOs que apareceram na 1ª rodada
SELECT g.codgeraloper, g.descricao, g.tipcgo, g.tipuso, g.status,
       g.indfixoabcmovimentacao, g.indtipoavaria, g.indtipocgomovto, g.acmcompravenda
  FROM max_codgeraloper g
 WHERE g.codgeraloper IN (43, 44, 46, 105, 403, 518, 519, 549, 551, 552, 553, 554,
                          555, 556, 559, 562, 809, 812, 865)
 ORDER BY g.codgeraloper;

--    B2) distribuição de valores das flags (para entender o que significam)
SELECT indfixoabcmovimentacao, COUNT(*) AS qtd FROM max_codgeraloper GROUP BY indfixoabcmovimentacao;
SELECT indtipoavaria,          COUNT(*) AS qtd FROM max_codgeraloper GROUP BY indtipoavaria;

--    B3) o "ABC de movimentação" pode ter uma tabela de configuração própria
SELECT owner, table_name FROM all_tables
 WHERE table_name LIKE '%ABC%MOV%' OR table_name LIKE '%MOV%ABC%'
 ORDER BY 1, 2;

-- C) TIPOS DE LOCAL: nome dos locais por tipo, para confirmar T = troca e L = loja
SELECT tiplocal, MIN(local) AS exemplo_1, MAX(local) AS exemplo_2, COUNT(*) AS qtd
  FROM mrl_local
 GROUP BY tiplocal
 ORDER BY tiplocal;

-- D) VOLUME DE TESTE: avarias de 1 loja em 1 dia, com a consulta corrigida.
--    Mostra se o filtro de CGO x local funciona antes de rodar o período inteiro.
--    Troque a loja (10) e o dia se quiser. Filtro de data sem função na coluna.
SELECT l.codgeraloper, lo.tiplocal, COUNT(*) AS lanctos,
       SUM(NVL(l.valorvlrnf, 0) + NVL(l.valoripi, 0) + NVL(l.valoricmsst, 0)
         + NVL(l.valordespnf, 0) + NVL(l.valoriss, 0) + NVL(l.valordespforanf, 0)
         - NVL(l.valordctoforanf, 0)) AS valor
  FROM mrl_lanctoestoque l
  JOIN mrl_local lo ON lo.nroempresa = l.nroempresa AND lo.seqlocal = l.local
 WHERE l.nroempresa = 10
   AND l.dtaentradasaida >= DATE '2026-09-15'
   AND l.dtaentradasaida <  DATE '2026-09-16'
   AND l.codgeraloper IN (403, 552, 519, 549, 551, 553, 559)
 GROUP BY l.codgeraloper, lo.tiplocal
 ORDER BY 1, 2;
