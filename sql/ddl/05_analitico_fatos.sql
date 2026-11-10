-- =============================================================================
-- 05_analitico_fatos.sql — fatos
-- Cada fato tem a granularidade da sua fonte e uma chave primária natural.
-- A PK natural é o que garante a idempotência: recarregar o mesmo dado
-- atualiza a mesma linha em vez de duplicar.
-- seq_categoria fica gravado no fato (categoria vigente na carga) para que o
-- índice por categoria não dependa de passar pelo produto.
-- =============================================================================

-- Avaria identificada: loja x produto x data x CGO
CREATE TABLE IF NOT EXISTS analitico.fato_avaria (
    nro_empresa     INTEGER NOT NULL REFERENCES analitico.dim_loja(nro_empresa),
    seq_produto     BIGINT  NOT NULL REFERENCES analitico.dim_produto(seq_produto),
    data            DATE    NOT NULL REFERENCES analitico.dim_data(data),
    cgo             INTEGER NOT NULL,
    seq_categoria   INTEGER NOT NULL REFERENCES analitico.dim_categoria(seq_categoria),
    qtd_lancada     NUMERIC(18,3) NOT NULL,
    vlr_avaria      NUMERIC(18,2) NOT NULL,
    id_carga        BIGINT NOT NULL REFERENCES controle.carga(id_carga),
    dt_atualizacao  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (nro_empresa, seq_produto, data, cgo)
);
CREATE INDEX IF NOT EXISTS ix_fato_avaria_data      ON analitico.fato_avaria (data);
CREATE INDEX IF NOT EXISTS ix_fato_avaria_loja_cat  ON analitico.fato_avaria (nro_empresa, seq_categoria, data);

-- Venda líquida: loja x categoria x dia (granularidade do ABC de Venda Sintético)
CREATE TABLE IF NOT EXISTS analitico.fato_venda (
    nro_empresa        INTEGER NOT NULL REFERENCES analitico.dim_loja(nro_empresa),
    seq_categoria      INTEGER NOT NULL REFERENCES analitico.dim_categoria(seq_categoria),
    data               DATE    NOT NULL REFERENCES analitico.dim_data(data),
    vlr_venda_bruta    NUMERIC(18,2) NOT NULL,
    vlr_devolucao      NUMERIC(18,2) NOT NULL,
    vlr_venda_liquida  NUMERIC(18,2) NOT NULL,
    id_carga           BIGINT NOT NULL REFERENCES controle.carga(id_carga),
    dt_atualizacao     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (nro_empresa, seq_categoria, data)
);
CREATE INDEX IF NOT EXISTS ix_fato_venda_data ON analitico.fato_venda (data);

-- Perda não identificada (inventário): loja x produto x data do inventário
-- vlr_divergente guarda o sinal original (sobra > 0, falta < 0) para auditoria;
-- vlr_falta é a regra de negócio: só faltas, em valor absoluto.
CREATE TABLE IF NOT EXISTS analitico.fato_perda_inventario (
    nro_empresa      INTEGER NOT NULL REFERENCES analitico.dim_loja(nro_empresa),
    seq_produto      BIGINT  NOT NULL REFERENCES analitico.dim_produto(seq_produto),
    data             DATE    NOT NULL REFERENCES analitico.dim_data(data),
    seq_categoria    INTEGER NOT NULL REFERENCES analitico.dim_categoria(seq_categoria),
    vlr_divergente   NUMERIC(18,2) NOT NULL,
    vlr_falta        NUMERIC(18,2) GENERATED ALWAYS AS (CASE WHEN vlr_divergente < 0 THEN -vlr_divergente ELSE 0 END) STORED,
    aba_origem       VARCHAR(40) NOT NULL,       -- permite substituir só a aba que mudou
    arquivo_origem   TEXT NOT NULL,
    linha_origem     INTEGER NOT NULL,           -- rastreabilidade até a linha do Excel
    id_carga         BIGINT NOT NULL REFERENCES controle.carga(id_carga),
    dt_atualizacao   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (nro_empresa, seq_produto, data)
);
CREATE INDEX IF NOT EXISTS ix_fato_perda_data ON analitico.fato_perda_inventario (data);
CREATE INDEX IF NOT EXISTS ix_fato_perda_aba  ON analitico.fato_perda_inventario (aba_origem);
