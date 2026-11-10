-- =============================================================================
-- 06_analitico_views.sql — views de consumo (Power BI e análises)
-- =============================================================================

-- Índice de perda mensal no grão de cálculo: loja x categoria x mês.
-- UNION ALL + GROUP BY em vez de FULL JOIN: uma combinação que só tem perda
-- (sem venda) ou só venda (sem perda) continua aparecendo.
-- Agregações acima deste grão (regional, rede) devem SOMAR perdas e vendas e
-- dividir depois (razão das somas), nunca tirar média dos índices.
CREATE OR REPLACE VIEW analitico.vw_indice_perda_mensal AS
WITH base AS (
    SELECT nro_empresa, seq_categoria, date_trunc('month', data)::date AS mes,
           vlr_venda_liquida AS venda, 0::numeric AS avaria, 0::numeric AS perda_ni
    FROM analitico.fato_venda
    UNION ALL
    SELECT nro_empresa, seq_categoria, date_trunc('month', data)::date, 0, vlr_avaria, 0
    FROM analitico.fato_avaria
    UNION ALL
    SELECT nro_empresa, seq_categoria, date_trunc('month', data)::date, 0, 0, vlr_falta
    FROM analitico.fato_perda_inventario
)
SELECT b.mes,
       to_char(b.mes, 'YYYY-MM')               AS ano_mes,
       l.nro_regional,
       r.nome_regional,
       b.nro_empresa,
       l.nome_loja,
       c.categoria,
       SUM(b.venda)                            AS venda_liquida,
       SUM(b.avaria)                           AS avaria_identificada,
       SUM(b.perda_ni)                         AS perda_nao_identificada,
       SUM(b.avaria) + SUM(b.perda_ni)         AS perda_total,
       (SUM(b.avaria) + SUM(b.perda_ni)) / NULLIF(SUM(b.venda), 0) AS indice_perda
FROM base b
JOIN analitico.dim_loja      l ON l.nro_empresa   = b.nro_empresa
JOIN analitico.dim_regional  r ON r.nro_regional  = l.nro_regional
JOIN analitico.dim_categoria c ON c.seq_categoria = b.seq_categoria
GROUP BY b.mes, l.nro_regional, r.nome_regional, b.nro_empresa, l.nome_loja, c.categoria;

-- -----------------------------------------------------------------------------
-- Views de controle para o painel. As datas/horas saem JÁ no horário de Brasília
-- (timestamp sem fuso): o conector de PostgreSQL do Power BI trata timestamptz de
-- forma ambígua (converte para o fuso da máquina ou para UTC, conforme a versão).
-- Converter aqui, perto da fonte, deixa uma regra só e sem ambiguidade.
-- DROP antes do CREATE: CREATE OR REPLACE não permite mudar o tipo de uma coluna.
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS controle.vw_ultima_carga;
DROP VIEW IF EXISTS controle.vw_ultimo_sucesso;
DROP VIEW IF EXISTS controle.vw_rejeitado_vigente;

-- Última carga de cada fonte (painel de qualidade).
CREATE VIEW controle.vw_ultima_carga AS
SELECT DISTINCT ON (fonte, COALESCE(aba, ''))
       fonte, aba, arquivo, status, periodo_inicio, periodo_fim,
       inicio AT TIME ZONE 'America/Sao_Paulo' AS inicio,
       fim    AT TIME ZONE 'America/Sao_Paulo' AS fim,
       linhas_lidas, linhas_carregadas, linhas_rejeitadas,
       linhas_inseridas, linhas_atualizadas, linhas_removidas, mensagem
FROM controle.carga
WHERE status <> 'IGNORADA'
ORDER BY fonte, COALESCE(aba, ''), carga.inicio DESC;

-- Último sucesso de cada fonte: "o painel está atualizado até quando?"
CREATE VIEW controle.vw_ultimo_sucesso AS
SELECT fonte, MAX(fim) AT TIME ZONE 'America/Sao_Paulo' AS dt_ultima_carga_ok
FROM controle.carga
WHERE status = 'SUCESSO'
GROUP BY fonte;

-- Rejeitados vigentes: os da última carga bem-sucedida de cada fonte/aba.
-- (Quando chega nova versão da planilha, os rejeitados da versão anterior
--  deixam de ser vigentes, mas continuam guardados para histórico.)
CREATE VIEW controle.vw_rejeitado_vigente AS
WITH ultima AS (
    SELECT DISTINCT ON (fonte, COALESCE(aba, '')) id_carga
    FROM controle.carga
    WHERE status = 'SUCESSO'
    ORDER BY fonte, COALESCE(aba, ''), inicio DESC
)
SELECT r.id_rejeitado, r.id_carga, r.fonte, r.arquivo, r.aba, r.linha_origem,
       r.motivo, m.tipo AS tipo_motivo, m.descricao AS descricao_motivo,
       r.detalhe, r.registro_original::text AS registro_original,
       r.dt_registro AT TIME ZONE 'America/Sao_Paulo' AS dt_registro
FROM controle.rejeitado r
JOIN ultima u ON u.id_carga = r.id_carga
JOIN controle.motivo_rejeicao m ON m.motivo = r.motivo;
