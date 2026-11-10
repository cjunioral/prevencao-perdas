-- =============================================================================
-- 08_rastrear_abc_venda.sql — achar a lógica real do "ABC de Venda Sintético"
--
-- O SQL Monitor mostrou que a tela (frmAnlABCDistribSint) só grava parâmetros
-- (MBIX_TABCATRIBCONSULTA, GEX_DADOSTEMPORARIOS) e lê o resultado
-- (MBI_TABCSINTETICA -> MBIX_TABCSINTETICA). O cálculo roda numa procedure no
-- servidor (~42 s), invisível ao SQL Monitor. Estas consultas acham essa lógica.
-- Todas leem só o dicionário de dados ou o resultado já calculado: custo baixo.
--
-- Parâmetros observados no rastro (consulta 743190, loja 10, 08/11/2026):
--   NRODIVISAO=1 | SEGMENTOS=1..13 (todos) | TIPCATEGORIA=M (mercadológica)
--   INDSUBTRAIICMSSTVLRVENDA=N (não subtrai ICMS ST) | vsPDSubtraiDescAcordoVerbaPdv=N
--   vsIndDescTransf=S (desconsidera transferências?) | vsPDPercPropBaixaProdABC=S
--   TIPOAPURACAO=L | vsMetodoPrecificacao=L | TIPOVISEMB=U | DETALHE1=PRODUTO
-- =============================================================================

-- 1) Qual objeto calcula o relatório?
SELECT owner, name, type, MIN(line) AS linha
  FROM all_source
 WHERE UPPER(text) LIKE '%MBI_TABCSINTETICA%'
    OR UPPER(text) LIKE '%ABCDISTRIBSINT%'
 GROUP BY owner, name, type
 ORDER BY owner, name;

-- 2) Trechos relevantes do código (troque o nome/tipo pelo achado no passo 1)
SELECT line, text
  FROM all_source
 WHERE owner = 'CONSINCO' AND name = '<NOME>' AND type = '<TIPO>'
   AND (UPPER(text) LIKE '%VLRVENDALIQ%' OR UPPER(text) LIKE '%FROM %'
        OR UPPER(text) LIKE '%TRANSF%' OR UPPER(text) LIKE '%SEGMENTO%'
        OR UPPER(text) LIKE '%ICMSST%' OR UPPER(text) LIKE '%DEVOL%')
 ORDER BY line;

-- 3) Se o código estiver protegido (wrap): de quais tabelas/views ele depende?
SELECT referenced_owner, referenced_name, referenced_type
  FROM all_dependencies
 WHERE name = '<NOME>' AND referenced_type IN ('TABLE', 'VIEW')
 ORDER BY referenced_name;

-- 4) Melhor fonte: o SQL interno executado (V$SQL guarda também o SQL recursivo
--    das procedures). Rode o relatório na tela e, em seguida (pedir grant ao DBA):
-- SELECT sql_id, last_active_time, sql_fulltext
--   FROM v$sql
--  WHERE UPPER(sql_fulltext) LIKE '%MBI_TABCSINTETICA%'
--    AND last_active_time > SYSDATE - 10/1440
--  ORDER BY last_active_time DESC;

-- 5) O resultado da tela fica guardado? (temporary = 'N' -> dá para consultar)
SELECT table_name, temporary, duration
  FROM all_tables
 WHERE table_name IN ('MBI_TABCSINTETICA', 'MBIX_TABCSINTETICA', 'GEX_DADOSTEMPORARIOS');

-- 6) Conferência automática: resultado da TELA por categoria, a partir do número
--    da consulta (SEQCONSULTA) que a tela gerou. Rodar o relatório com o mês
--    inteiro e DETALHE1 = PRODUTO, uma loja por vez.
--    >>> VALIDAR: SEQDETALHE1 = SEQPRODUTO quando DETALHE1 = PRODUTO.
SELECT c.seqcategoria, c.categoria,
       SUM(t.vlrvenda)    AS venda_tela,
       SUM(t.vlrvendaliq) AS venda_liquida_tela
  FROM mbix_tabcsintetica t
  JOIN map_produto p      ON p.seqproduto   = t.seqdetalhe1
  JOIN map_famdivcateg fc ON fc.seqfamilia  = p.seqfamilia
                         AND fc.nrodivisao  = 1
                         AND fc.status      = 'A'
  JOIN map_categoria c    ON c.seqcategoria = fc.seqcategoria
                         AND c.nrodivisao   = fc.nrodivisao
                         AND c.nivelhierarquia = 1
 WHERE t.seqconsulta = :seqconsulta
   AND c.seqcategoria IN (11, 24)
 GROUP BY c.seqcategoria, c.categoria;

-- Conferência de sanidade: total da loja na tela (todas as categorias)
SELECT COUNT(*) AS linhas, SUM(vlrvenda) AS venda, SUM(vlrvendaliq) AS venda_liquida
  FROM mbix_tabcsintetica
 WHERE seqconsulta = :seqconsulta;
