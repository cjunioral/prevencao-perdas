-- =============================================================================
-- 07_permissoes.sql — papel somente leitura para o Power BI
-- O Power BI não precisa (nem deve) escrever no banco. Crie um usuário de login
-- e conceda este papel:  CREATE USER powerbi WITH PASSWORD '...' IN ROLE leitura_bi;
-- (a senha não fica versionada).
-- =============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leitura_bi') THEN
        CREATE ROLE leitura_bi NOLOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA analitico, controle TO leitura_bi;
GRANT SELECT ON ALL TABLES IN SCHEMA analitico, controle TO leitura_bi;
ALTER DEFAULT PRIVILEGES IN SCHEMA analitico GRANT SELECT ON TABLES TO leitura_bi;
ALTER DEFAULT PRIVILEGES IN SCHEMA controle  GRANT SELECT ON TABLES TO leitura_bi;
