-- =============================================================================
-- 02_controle.sql — tabelas de controle de carga e de rejeitados
-- =============================================================================

-- Uma linha por execução do processo (python etl.py).
CREATE TABLE IF NOT EXISTS controle.execucao (
    id_execucao      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    inicio           TIMESTAMPTZ NOT NULL DEFAULT now(),
    fim              TIMESTAMPTZ,
    status           VARCHAR(20) NOT NULL DEFAULT 'EM_ANDAMENTO'
                     CHECK (status IN ('EM_ANDAMENTO','SUCESSO','SUCESSO_PARCIAL','FALHA','BLOQUEADA')),
    modo             VARCHAR(20) NOT NULL,              -- diario | completo
    data_referencia  DATE NOT NULL,                     -- "hoje" do ponto de vista da carga
    host             VARCHAR(100),
    pid              INTEGER,
    parametros       JSONB,
    mensagem         TEXT
);

-- Uma linha por fonte (e por arquivo/aba no caso da planilha) em cada execução.
CREATE TABLE IF NOT EXISTS controle.carga (
    id_carga            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_execucao         BIGINT NOT NULL REFERENCES controle.execucao(id_execucao),
    fonte               VARCHAR(40) NOT NULL,           -- consinco_avaria, planilha_inventario...
    arquivo             TEXT,                           -- nome do arquivo (planilha)
    aba                 TEXT,                           -- aba da planilha
    hash_arquivo        CHAR(64),                       -- SHA-256: detecta nova versão
    periodo_inicio      DATE,
    periodo_fim         DATE,
    inicio              TIMESTAMPTZ NOT NULL DEFAULT now(),
    fim                 TIMESTAMPTZ,
    status              VARCHAR(20) NOT NULL DEFAULT 'EM_ANDAMENTO'
                        CHECK (status IN ('EM_ANDAMENTO','SUCESSO','FALHA','IGNORADA')),
    linhas_lidas        INTEGER NOT NULL DEFAULT 0,
    linhas_carregadas   INTEGER NOT NULL DEFAULT 0,
    linhas_rejeitadas   INTEGER NOT NULL DEFAULT 0,
    linhas_inseridas    INTEGER NOT NULL DEFAULT 0,    -- efeito no analítico
    linhas_atualizadas  INTEGER NOT NULL DEFAULT 0,
    linhas_removidas    INTEGER NOT NULL DEFAULT 0,
    avisos              JSONB,                          -- contagens de tratamentos aplicados
    mensagem            TEXT                            -- erro ou motivo de IGNORADA
);
CREATE INDEX IF NOT EXISTS ix_carga_fonte_inicio ON controle.carga (fonte, inicio DESC);
CREATE INDEX IF NOT EXISTS ix_carga_execucao     ON controle.carga (id_execucao);

-- Catálogo de motivos: documenta o tratamento e alimenta o painel de qualidade.
CREATE TABLE IF NOT EXISTS controle.motivo_rejeicao (
    motivo      VARCHAR(40) PRIMARY KEY,
    tipo        VARCHAR(20) NOT NULL CHECK (tipo IN ('ESTRUTURA','QUALIDADE','CRUZAMENTO','REGRA_NEGOCIO')),
    descricao   TEXT NOT NULL
);

-- Linhas que não entraram no analítico. Nada some sem registro.
CREATE TABLE IF NOT EXISTS controle.rejeitado (
    id_rejeitado       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_carga           BIGINT NOT NULL REFERENCES controle.carga(id_carga),
    fonte              VARCHAR(40) NOT NULL,
    arquivo            TEXT,
    aba                TEXT,
    linha_origem       INTEGER,                         -- nº da linha no Excel / nº do registro
    registro_original  JSONB NOT NULL,                  -- a linha como veio
    motivo             VARCHAR(40) NOT NULL REFERENCES controle.motivo_rejeicao(motivo),
    detalhe            TEXT,
    dt_registro        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_rejeitado_carga  ON controle.rejeitado (id_carga);
CREATE INDEX IF NOT EXISTS ix_rejeitado_motivo ON controle.rejeitado (motivo);

INSERT INTO controle.motivo_rejeicao (motivo, tipo, descricao) VALUES
  ('LOJA_AUSENTE',            'QUALIDADE',     'Linha sem loja informada'),
  ('LOJA_NAO_ENCONTRADA',     'CRUZAMENTO',    'Loja informada não existe no cadastro da Consinco'),
  ('PRODUTO_AUSENTE',         'QUALIDADE',     'Linha sem código de produto'),
  ('PRODUTO_NAO_ENCONTRADO',  'CRUZAMENTO',    'Código não corresponde a produto nem a EAN da Consinco'),
  ('PRODUTO_FORA_ESCOPO',     'REGRA_NEGOCIO', 'Produto existe, mas a categoria na Consinco não é Açougue/Hortifruti'),
  ('PRODUTO_SEM_CATEGORIA',   'CRUZAMENTO',    'Produto sem ligação ativa família x categoria'),
  ('DATA_AUSENTE',            'QUALIDADE',     'Linha sem data de inventário'),
  ('DATA_INVALIDA',           'QUALIDADE',     'Data de inventário ilegível ou fora do intervalo plausível'),
  ('FORA_DO_PERIODO',         'REGRA_NEGOCIO', 'Data de inventário fora do período de análise configurado'),
  ('VALOR_AUSENTE',           'QUALIDADE',     'Valor divergente em branco'),
  ('VALOR_INVALIDO',          'QUALIDADE',     'Valor divergente não numérico (texto, erro de fórmula #N/D, #REF!)'),
  ('LINHA_DUPLICADA',         'QUALIDADE',     'Linha idêntica a outra já lida (mesma loja, produto, data e valor)'),
  ('DUPLICIDADE_CONFLITANTE', 'QUALIDADE',     'Mesma loja, produto e data com valores diferentes'),
  ('LINHA_TOTALIZADORA',      'ESTRUTURA',     'Linha de total/subtotal da planilha (não é dado de produto)'),
  ('CABECALHO_REPETIDO',      'ESTRUTURA',     'Cabeçalho repetido no meio da aba'),
  ('LINHA_SEM_DADOS',         'ESTRUTURA',     'Linha sem loja, produto, data e valor (ex.: observação solta abaixo da tabela)'),
  ('LOJA_NAO_CADASTRADA',     'CRUZAMENTO',    'Registro da Consinco com loja ausente da dimensão de lojas'),
  ('VALOR_NULO_CONSINCO',     'QUALIDADE',     'Registro da Consinco com valor nulo')
ON CONFLICT (motivo) DO UPDATE SET tipo = EXCLUDED.tipo, descricao = EXCLUDED.descricao;
