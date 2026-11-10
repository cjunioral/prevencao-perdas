-- =============================================================================
-- 05_vendas.sql — venda líquida por loja x categoria x dia
-- Contrato: nro_empresa, seq_categoria, dta_venda, vlr_venda_bruta,
--           vlr_devolucao, vlr_venda_liquida
--
-- Base: a mesma lógica do relatório "ABC de Venda Sintético".
-- COMO GARANTIR QUE BATE (fazer nesta ordem):
--   1. Capture o SQL que o relatório executa (00_descoberta.sql, passo 9, ou
--      peça ao DBA um trace da sessão). Copie de lá: a view/tabela base, os
--      filtros de CGO e a fórmula de venda líquida (devoluções, impostos,
--      descontos). Os parâmetros marcados na tela mudam o número.
--   2. Na falta do SQL, a base usual do ABC é a view MAXV_ABCDISTRIBBASE, com
--      venda líquida = valor dos itens - valor das devoluções (abaixo).
--   3. Rode 06_conferencia_abc.sql e compare com a tela (mesmo período, loja e
--      categoria). Registre a comparação no README. Diferença != 0 -> investigar
--      antes de seguir (parâmetros da tela, CGOs, devoluções, data usada).
--
-- Parâmetros da tela capturados no SQL Monitor (ver 08_rastrear_abc_venda.sql):
--   todos os segmentos (1..13) -> sem filtro de segmento aqui;
--   INDSUBTRAIICMSSTVLRVENDA = N -> ICMS ST NÃO é subtraído (como abaixo);
--   vsPDSubtraiDescAcordoVerbaPdv = N -> verba de acordo do PDV NÃO é subtraída;
--   vsIndDescTransf = S -> provavelmente desconsidera TRANSFERÊNCIAS entre lojas:
--      >>> VALIDAR e, se confirmado, excluir os CGOs de transferência;
--   vsPDPercPropBaixaProdABC = S -> baixa proporcional de produto composto
--      (pode afetar Açougue: desmembramento) >>> VALIDAR no código da procedure.
-- O resultado da tela fica em MBIX_TABCSINTETICA (SEQCONSULTA): a conferência
-- pode ser feita por SQL (08_rastrear_abc_venda.sql, passo 6).
-- >>> VALIDAR: view, colunas e filtros contra o SQL do relatório.
-- =============================================================================
SELECT v.nroempresa                                        AS nro_empresa,
       c.seqcategoria                                      AS seq_categoria,
       TRUNC(v.dtavda)                                     AS dta_venda,
       SUM(NVL(v.vlritem, 0))                              AS vlr_venda_bruta,
       SUM(NVL(v.vlrdevolitem, 0))                         AS vlr_devolucao,
       SUM(NVL(v.vlritem, 0)) - SUM(NVL(v.vlrdevolitem, 0)) AS vlr_venda_liquida
  FROM maxv_abcdistribbase v                               -- >>> VALIDAR
  JOIN max_empresa e      ON e.nroempresa   = v.nroempresa
  JOIN map_produto p      ON p.seqproduto   = v.seqproduto
  JOIN map_famdivcateg fc ON fc.seqfamilia  = p.seqfamilia
                         AND fc.nrodivisao  = e.nrodivisao
                         AND fc.status      = 'A'
  JOIN map_categoria c    ON c.seqcategoria = fc.seqcategoria
                         AND c.nrodivisao   = fc.nrodivisao
                         AND c.nivelhierarquia = :nivel_categoria
 WHERE v.dtavda >= :dt_ini
   AND v.dtavda <  :dt_fim
   AND c.seqcategoria IN (:categorias)
 GROUP BY v.nroempresa, c.seqcategoria, TRUNC(v.dtavda)
