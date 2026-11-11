-- =============================================================================
-- 01_lojas.sql — cadastro de lojas com a regional
-- Contrato de saída (o ETL depende destes aliases):
--   nro_empresa, nome_loja, nro_regional, nome_regional, nro_divisao, cidade, uf, status
-- Cadastro pequeno (58 empresas): leitura completa é aceitável.
--
-- REGIONAL: a Consinco não tem cadastro de regional preenchido (investigação em
-- docs/descoberta_consinco.md). A regra vem da área de negócio: lista de lojas por regional
-- de uma aplicação interna, revisada com a operação em 11/11/2026.
--   * NÃO é geográfica: 019 (Assu) e 027 (Macau) são da Regional Natal; 030 (Juazeiro, CE)
--     está na Regional Mossoró "por enquanto";
--   * por isso a regra é por NÚMERO DA LOJA, não por cidade ou UF;
--   * empresas fora da lista (depósitos, estoques, operações que não são supermercado)
--     ficam sem regional: o ETL as grava como -1 "SEM REGIONAL" e elas entram só no
--     total da rede, sem distorcer nenhuma regional.
-- Quando a regional for cadastrada na Consinco, só este CASE muda.
-- =============================================================================
SELECT e.nroempresa                         AS nro_empresa,
       e.nomereduzido                       AS nome_loja,
       CASE
         WHEN e.nroempresa IN (1, 3, 6, 7, 8, 9, 10, 11, 26, 30, 41)             THEN 1
         WHEN e.nroempresa IN (2, 12, 13, 14, 16, 19, 20, 22, 27, 42)             THEN 2
         WHEN e.nroempresa IN (4, 5, 15, 17, 18, 21, 23, 24, 25, 28, 40)          THEN 3
       END                                  AS nro_regional,      -- NULL = sem regional
       CASE
         WHEN e.nroempresa IN (1, 3, 6, 7, 8, 9, 10, 11, 26, 30, 41)             THEN 'REGIONAL MOSSORÓ'
         WHEN e.nroempresa IN (2, 12, 13, 14, 16, 19, 20, 22, 27, 42)             THEN 'REGIONAL NATAL'
         WHEN e.nroempresa IN (4, 5, 15, 17, 18, 21, 23, 24, 25, 28, 40)          THEN 'REGIONAL PARAÍBA'
       END                                  AS nome_regional,
       e.nrodivisao                         AS nro_divisao,
       e.cidade                             AS cidade,
       e.uf                                 AS uf,
       e.status                             AS status
  FROM max_empresa e
