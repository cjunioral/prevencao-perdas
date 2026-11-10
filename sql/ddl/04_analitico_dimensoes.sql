-- =============================================================================
-- 04_analitico_dimensoes.sql — dimensões do modelo estrela
-- =============================================================================

CREATE TABLE IF NOT EXISTS analitico.dim_data (
    data          DATE PRIMARY KEY,
    ano           SMALLINT NOT NULL,
    mes           SMALLINT NOT NULL,
    ano_mes       CHAR(7)  NOT NULL,      -- 2026-09 (ordena corretamente como texto)
    nome_mes      VARCHAR(12) NOT NULL,   -- Setembro
    mes_ano       VARCHAR(10) NOT NULL,   -- set/2026 (rótulo para o painel)
    inicio_mes    DATE NOT NULL,
    trimestre     SMALLINT NOT NULL,
    dia           SMALLINT NOT NULL,
    dia_semana    SMALLINT NOT NULL,      -- 1=segunda ... 7=domingo (ISO)
    nome_dia      VARCHAR(10) NOT NULL
);

-- Calendário fixo (cobre histórico da planilha e os próximos anos).
INSERT INTO analitico.dim_data
SELECT d::date,
       EXTRACT(YEAR FROM d)::smallint,
       EXTRACT(MONTH FROM d)::smallint,
       to_char(d, 'YYYY-MM'),
       (ARRAY['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho',
              'Agosto','Setembro','Outubro','Novembro','Dezembro'])[EXTRACT(MONTH FROM d)],
       (ARRAY['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'])[EXTRACT(MONTH FROM d)]
           || '/' || EXTRACT(YEAR FROM d),
       date_trunc('month', d)::date,
       EXTRACT(QUARTER FROM d)::smallint,
       EXTRACT(DAY FROM d)::smallint,
       EXTRACT(ISODOW FROM d)::smallint,
       (ARRAY['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo'])[EXTRACT(ISODOW FROM d)]
FROM generate_series(DATE '2024-01-01', DATE '2028-12-31', INTERVAL '1 day') AS g(d)
ON CONFLICT (data) DO NOTHING;

CREATE TABLE IF NOT EXISTS analitico.dim_regional (
    nro_regional   INTEGER PRIMARY KEY,
    nome_regional  VARCHAR(100) NOT NULL,
    dt_atualizacao TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Membro "sem regional": loja sem regional cadastrada não some do painel.
INSERT INTO analitico.dim_regional (nro_regional, nome_regional)
VALUES (-1, 'SEM REGIONAL') ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS analitico.dim_loja (
    nro_empresa    INTEGER PRIMARY KEY,
    nome_loja      VARCHAR(100) NOT NULL,
    nro_regional   INTEGER NOT NULL DEFAULT -1 REFERENCES analitico.dim_regional(nro_regional),
    cidade         VARCHAR(100),
    uf             CHAR(2),
    ativa          BOOLEAN NOT NULL DEFAULT TRUE,
    dt_atualizacao TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_dim_loja_regional ON analitico.dim_loja (nro_regional);

CREATE TABLE IF NOT EXISTS analitico.dim_categoria (
    seq_categoria   INTEGER PRIMARY KEY,
    nome_categoria  VARCHAR(100) NOT NULL,          -- como está na Consinco
    categoria       VARCHAR(20)  NOT NULL           -- rótulo padronizado do escopo
                    CHECK (categoria IN ('AÇOUGUE','HORTIFRUTI')),
    dt_atualizacao  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analitico.dim_produto (
    seq_produto     BIGINT PRIMARY KEY,
    desc_produto    VARCHAR(200),
    seq_familia     BIGINT,
    seq_categoria   INTEGER REFERENCES analitico.dim_categoria(seq_categoria),
    dt_atualizacao  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_dim_produto_categoria ON analitico.dim_produto (seq_categoria);

-- Códigos de barras (EAN) -> produto. Usado no cruzamento da planilha.
CREATE TABLE IF NOT EXISTS analitico.produto_codigo (
    cod_acesso   VARCHAR(30) NOT NULL,
    seq_produto  BIGINT NOT NULL REFERENCES analitico.dim_produto(seq_produto),
    PRIMARY KEY (cod_acesso, seq_produto)
);
