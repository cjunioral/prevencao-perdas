-- =============================================================================
-- 04_avarias.sql — avarias identificadas (lançamentos de estoque)
-- Grão de saída: loja x produto x data x CGO
-- Contrato: nro_empresa, seq_produto, dta_lancamento, cgo, seq_categoria,
--           qtd_lancada, vlr_movimentacao
--
-- Regras do enunciado, na ordem em que aparecem no WHERE:
--   1. só CGOs de avaria (:cgos) marcados para entrar no ABC de movimentação;
--   2. CGO 403 só com local tipo 'T'; CGO 552 só com local tipo 'L'
--      (os demais CGOs de avaria, se houver, entram em qualquer local);
--   3. valor = NF + IPI + ICMS ST + despesas na NF + ISS + despesas fora da NF
--      - descontos fora da NF. Cada parcela passa por NVL: no Oracle,
--      número + NULL = NULL, e um único imposto nulo zeraria a linha inteira;
--   4. categoria pela família, só ligação ativa, no nível configurado;
--   5. só Açougue e Hortifruti.
--
-- Cuidado com a produção:
--   * filtro por intervalo semiaberto na coluna de data SEM função
--     (col >= :dt_ini AND col < :dt_fim) -> usa índice e pega o dia inteiro
--     mesmo que a coluna tenha hora; TRUNC(col) no WHERE impediria o índice;
--   * o ETL chama esta consulta em blocos de poucos dias (BLOCO_EXTRACAO_DIAS);
--   * bind variables (:dt_ini...) -> o Oracle reaproveita o plano.
--
-- >>> VALIDAR com 00_descoberta.sql: nomes das colunas de valor, da data, do
--     local e da flag de ABC de movimentação.
-- =============================================================================
SELECT l.nroempresa                       AS nro_empresa,
       l.seqproduto                       AS seq_produto,
       TRUNC(l.dtaentradasaida)           AS dta_lancamento,   -- >>> VALIDAR coluna de data
       l.codgeraloper                     AS cgo,
       c.seqcategoria                     AS seq_categoria,
       SUM(NVL(l.qtdlancto, 0))           AS qtd_lancada,      -- >>> VALIDAR
       SUM(  NVL(l.vlrtotalnf, 0)                              -- valor da NF      >>> VALIDAR
           + NVL(l.vlripi, 0)                                  -- IPI
           + NVL(l.vlricmsst, 0)                               -- ICMS ST
           + NVL(l.vlrdespnf, 0)                               -- despesas na NF
           + NVL(l.vlriss, 0)                                  -- ISS
           + NVL(l.vlrdespforanf, 0)                           -- despesas fora da NF
           - NVL(l.vlrdescforanf, 0)                           -- descontos fora da NF
          )                               AS vlr_movimentacao
  FROM mrl_lanctoestoque l
  JOIN max_codgeraloper g ON g.codgeraloper = l.codgeraloper
  JOIN mrl_local lo       ON lo.nroempresa  = l.nroempresa
                         AND lo.seqlocal    = l.local          -- >>> VALIDAR coluna do local
  JOIN max_empresa e      ON e.nroempresa   = l.nroempresa
  JOIN map_produto p      ON p.seqproduto   = l.seqproduto
  JOIN map_famdivcateg fc ON fc.seqfamilia  = p.seqfamilia
                         AND fc.nrodivisao  = e.nrodivisao
                         AND fc.status      = 'A'
  JOIN map_categoria c    ON c.seqcategoria = fc.seqcategoria
                         AND c.nrodivisao   = fc.nrodivisao
                         AND c.nivelhierarquia = :nivel_categoria
 WHERE l.dtaentradasaida >= :dt_ini
   AND l.dtaentradasaida <  :dt_fim
   AND l.codgeraloper IN (:cgos)
   AND g.indabcmovto = 'S'                                     -- >>> VALIDAR flag ABC movimentação
   AND (   (l.codgeraloper = 403 AND lo.tiplocal = 'T')
        OR (l.codgeraloper = 552 AND lo.tiplocal = 'L')
        OR  l.codgeraloper NOT IN (403, 552))
   AND c.seqcategoria IN (:categorias)
 GROUP BY l.nroempresa, l.seqproduto, TRUNC(l.dtaentradasaida),
          l.codgeraloper, c.seqcategoria
