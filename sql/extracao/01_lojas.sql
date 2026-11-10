-- =============================================================================
-- 01_lojas.sql — cadastro de lojas com a regional
-- Contrato de saída (o ETL depende destes aliases):
--   nro_empresa, nome_loja, nro_regional, nome_regional, nro_divisao, cidade, uf, status
-- Cadastro pequeno: leitura completa é aceitável.
-- >>> VALIDAR com 00_descoberta.sql (passo 1): tabela/coluna da regional.
-- =============================================================================
SELECT e.nroempresa       AS nro_empresa,
       e.nomereduzido     AS nome_loja,
       e.nroregional      AS nro_regional,      -- >>> VALIDAR
       r.regional         AS nome_regional,     -- >>> VALIDAR
       e.nrodivisao       AS nro_divisao,
       e.cidade           AS cidade,
       e.uf               AS uf,
       e.status           AS status
  FROM max_empresa e
  LEFT JOIN max_regional r                      -- >>> VALIDAR
         ON r.nroregional = e.nroregional
