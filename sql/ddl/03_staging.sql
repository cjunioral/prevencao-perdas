-- =============================================================================
-- 03_staging.sql — dados como vieram das fontes
-- Cadastros: espelho da última extração (substituídos a cada carga).
-- Movimentos Consinco: a janela extraída substitui a mesma janela no staging.
-- Planilha: guarda a linha original (todas as colunas em JSONB) + campos-texto
--           extraídos, sem conversão. A conversão acontece no Python e o
--           resultado vai para o analítico ou para controle.rejeitado.
-- =============================================================================

CREATE TABLE IF NOT EXISTS staging.consinco_loja (
    nro_empresa     INTEGER PRIMARY KEY,
    nome_loja       TEXT,
    nro_regional    INTEGER,
    nome_regional   TEXT,
    nro_divisao     INTEGER,
    cidade          TEXT,
    uf              TEXT,
    status          TEXT,
    id_carga        BIGINT NOT NULL,
    dt_extracao     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS staging.consinco_produto (
    seq_produto     BIGINT PRIMARY KEY,
    desc_produto    TEXT,
    seq_familia     BIGINT,
    seq_categoria   INTEGER,          -- categoria no nível configurado (ligação ativa)
    nome_categoria  TEXT,
    id_carga        BIGINT NOT NULL,
    dt_extracao     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS staging.consinco_produto_codigo (
    cod_acesso      TEXT NOT NULL,    -- EAN/código de barras
    seq_produto     BIGINT NOT NULL,
    tip_codigo      TEXT,
    id_carga        BIGINT NOT NULL,
    PRIMARY KEY (cod_acesso, seq_produto)
);

CREATE TABLE IF NOT EXISTS staging.consinco_avaria (
    nro_empresa      INTEGER,
    seq_produto      BIGINT,
    dta_lancamento   DATE,
    cgo              INTEGER,
    seq_categoria    INTEGER,
    qtd_lancada      NUMERIC(18,3),
    vlr_movimentacao NUMERIC(18,2),
    id_carga         BIGINT NOT NULL,
    dt_extracao      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_stg_avaria_data ON staging.consinco_avaria (dta_lancamento);

CREATE TABLE IF NOT EXISTS staging.consinco_venda (
    nro_empresa       INTEGER,
    seq_categoria     INTEGER,
    dta_venda         DATE,
    vlr_venda_bruta   NUMERIC(18,2),
    vlr_devolucao     NUMERIC(18,2),
    vlr_venda_liquida NUMERIC(18,2),
    id_carga          BIGINT NOT NULL,
    dt_extracao       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_stg_venda_data ON staging.consinco_venda (dta_venda);

CREATE TABLE IF NOT EXISTS staging.planilha_inventario (
    id_carga          BIGINT NOT NULL,
    arquivo           TEXT NOT NULL,
    aba               TEXT NOT NULL,
    linha_origem      INTEGER NOT NULL,
    loja_texto        TEXT,
    produto_texto     TEXT,
    descricao_texto   TEXT,
    data_texto        TEXT,
    valor_texto       TEXT,
    registro_original JSONB NOT NULL,
    PRIMARY KEY (id_carga, linha_origem)
);
CREATE INDEX IF NOT EXISTS ix_stg_planilha_aba ON staging.planilha_inventario (aba);
