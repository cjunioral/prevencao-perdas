-- =============================================================================
-- 10_descoberta_parte3.sql — terceira rodada (10/11/2026)
-- Fecha: (A) onde está a regional, (B) quais CGOs marcados no ABC são avaria e
-- o peso de cada um, (C) os blocos 7 e 8 da 1ª rodada.
-- Blocos A e C: só dicionário/cadastro (leves).
-- Bloco B2: lê lançamentos de 1 loja x 1 semana (moderado). Se a consulta passar
-- de ~1 minuto, cancele (botão vermelho) e rode depois das 21h.
-- =============================================================================

-- A) REGIONAL ---------------------------------------------------------------
-- A1) as tabelas customizadas têm dados? (0 = vazias; erro = sem permissão)
SELECT 'CT_REGIONAIS' AS tabela, COUNT(*) AS linhas FROM ct_regionais
UNION ALL
SELECT 'CT_REGIONAISEMPRESAS', COUNT(*) FROM ct_regionaisempresas;

-- A2) qualquer tabela/view do sistema com coluna de regional ou região
SELECT owner, table_name, column_name
  FROM all_tab_columns
 WHERE (column_name LIKE '%REGIONAL%' OR column_name LIKE '%REGIAO%')
   AND owner = 'CONSINCO'
 ORDER BY table_name, column_name;

-- A3) views com REGIONAL no nome
SELECT owner, view_name FROM all_views
 WHERE view_name LIKE '%REGIONAL%' OR view_name LIKE '%REGIAO%'
 ORDER BY 1, 2;

-- A4) lojas com grupo e segmento: às vezes a "regional" é o grupo de empresas
SELECT e.nroempresa, e.nomereduzido, e.nrogrupoempresa, e.nrosegmentoprinc,
       e.nrodivisao, e.cidade, e.uf, e.status
  FROM max_empresa e
 ORDER BY e.nroempresa;

-- B) CGOs DE AVARIA ---------------------------------------------------------
-- B1) o campo INDTIPOCGOMOVTO ('AS' em 549, 552 e 562) parece classificar os CGOs
--     para o ABC de movimentação. Distribuição completa:
SELECT g.indtipocgomovto, g.indfixoabcmovimentacao, COUNT(*) AS qtd,
       LISTAGG(g.codgeraloper, ',') WITHIN GROUP (ORDER BY g.codgeraloper) AS cgos
  FROM max_codgeraloper g
 GROUP BY g.indtipocgomovto, g.indfixoabcmovimentacao
 ORDER BY 1, 2;

-- B2) peso de cada CGO marcado no ABC, só Açougue/Hortifruti, loja 10, 1 semana.
--     Mostra quais CGOs realmente movimentam essas categorias e quanto.
SELECT l.codgeraloper, g.descricao, g.indtipocgomovto, lo.tiplocal, c.categoria,
       COUNT(*) AS lanctos,
       ROUND(SUM(NVL(l.valorvlrnf, 0) + NVL(l.valoripi, 0) + NVL(l.valoricmsst, 0)
               + NVL(l.valordespnf, 0) + NVL(l.valoriss, 0) + NVL(l.valordespforanf, 0)
               - NVL(l.valordctoforanf, 0)), 2) AS valor,
       ROUND(MAX(NVL(l.valorvlrnf, 0)), 2) AS maior_lancto
  FROM mrl_lanctoestoque l
  JOIN max_codgeraloper g ON g.codgeraloper = l.codgeraloper
  JOIN mrl_local lo       ON lo.nroempresa  = l.nroempresa AND lo.seqlocal = l.local
  JOIN max_empresa e      ON e.nroempresa   = l.nroempresa
  JOIN map_produto p      ON p.seqproduto   = l.seqproduto
  JOIN map_famdivcateg fc ON fc.seqfamilia  = p.seqfamilia AND fc.nrodivisao = e.nrodivisao
                         AND fc.status = 'A'
  JOIN map_categoria c    ON c.seqcategoria = fc.seqcategoria AND c.nrodivisao = fc.nrodivisao
                         AND c.nivelhierarquia = 1
 WHERE l.nroempresa = 10
   AND l.dtaentradasaida >= DATE '2026-09-15'
   AND l.dtaentradasaida <  DATE '2026-09-22'
   AND g.indfixoabcmovimentacao = 'S'
   AND c.seqcategoria IN (11, 24)
 GROUP BY l.codgeraloper, g.descricao, g.indtipocgomovto, lo.tiplocal, c.categoria
 ORDER BY valor DESC;

-- B3) o lançamento grande do CGO 549 (loja 10, 15/09): que produto, que histórico?
SELECT l.seqmovtoestq, l.seqproduto, p.desccompleta, l.tiplancto, l.qtdlancto,
       l.valorvlrnf, l.historico, l.motivomovto, l.usulancto, l.dtahorlancto
  FROM mrl_lanctoestoque l
  JOIN map_produto p ON p.seqproduto = l.seqproduto
 WHERE l.nroempresa = 10
   AND l.dtaentradasaida >= DATE '2026-09-15'
   AND l.dtaentradasaida <  DATE '2026-09-16'
   AND l.codgeraloper = 549;

-- C) PENDENTES DA 1ª RODADA ---------------------------------------------------
-- C1) família com mais de uma ligação ativa no nível 1 (vazio = ótimo)
SELECT fc.seqfamilia, fc.nrodivisao, COUNT(*) AS ligacoes_ativas
  FROM map_famdivcateg fc
  JOIN map_categoria c ON c.seqcategoria = fc.seqcategoria AND c.nrodivisao = fc.nrodivisao
 WHERE fc.status = 'A' AND c.nivelhierarquia = 1
 GROUP BY fc.seqfamilia, fc.nrodivisao
HAVING COUNT(*) > 1;

-- C2) índices da tabela de lançamentos (a data do filtro precisa estar indexada)
SELECT index_name, column_name, column_position
  FROM all_ind_columns
 WHERE table_name = 'MRL_LANCTOESTOQUE'
 ORDER BY index_name, column_position;
