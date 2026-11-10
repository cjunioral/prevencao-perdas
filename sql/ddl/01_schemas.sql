-- =============================================================================
-- 01_schemas.sql
-- Três schemas, cada um com uma responsabilidade:
--   staging   -> dados como vieram de cada fonte (texto/valores brutos), para
--                auditoria e reprocessamento sem voltar na fonte.
--   analitico -> modelo dimensional tratado, consumido pelo Power BI e pelas
--                consultas de análise.
--   controle  -> metadados do processo: execuções, cargas por fonte/arquivo,
--                linhas rejeitadas e catálogo de motivos.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS controle;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analitico;

COMMENT ON SCHEMA controle  IS 'Controle de carga: execuções, cargas, rejeitados';
COMMENT ON SCHEMA staging   IS 'Dados como vieram de cada fonte (Consinco e planilha)';
COMMENT ON SCHEMA analitico IS 'Modelo dimensional tratado, fonte do Power BI';
