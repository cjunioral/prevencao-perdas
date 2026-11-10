-- =============================================================================
-- 01_lojas.sql — cadastro de lojas com a regional
-- Contrato de saída (o ETL depende destes aliases):
--   nro_empresa, nome_loja, nro_regional, nome_regional, nro_divisao, cidade, uf, status
-- Cadastro pequeno (58 empresas): leitura completa é aceitável.
--
-- REGIONAL — o que foi investigado (10/11/2026), sem cadastro preenchido:
--   * MAX_EMPRESA não tem coluna de regional;
--   * CT_REGIONAIS / CT_REGIONAISEMPRESAS (customizadas): existem, 0 linhas;
--   * MSUV_EMPRESASREGIAO (região de compra) e MAX_REGVDAEMP (região de venda): 0 linhas;
--   * GE_CIDADE.REGIAO: vazia; CONSINCOMONITOR.VW_REGIAO (monitor de PDV): vazia;
--   * NROSEGMENTOPRINC é canal de venda (SUPERMERCADO, ATACADO, CD...), não regional.
-- DECISÃO PROVISÓRIA: regional = UF da loja (dado da própria Consinco, com sentido
-- geográfico). Pendente de confirmação com a área. Quando a regional oficial for
-- informada, só esta consulta muda: o modelo, o ETL e o painel continuam iguais.
-- =============================================================================
SELECT e.nroempresa                         AS nro_empresa,
       e.nomereduzido                       AS nome_loja,
       CASE e.uf WHEN 'RN' THEN 1 WHEN 'PB' THEN 2 WHEN 'CE' THEN 3
                 WHEN 'PE' THEN 4 ELSE 9 END AS nro_regional,      -- provisório: por UF
       'REGIONAL ' || e.uf                  AS nome_regional,     -- provisório: por UF
       e.nrodivisao                         AS nro_divisao,
       e.cidade                             AS cidade,
       e.uf                                 AS uf,
       e.status                             AS status
  FROM max_empresa e
