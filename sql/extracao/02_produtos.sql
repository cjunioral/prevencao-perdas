-- =============================================================================
-- 02_produtos.sql — produtos de Açougue e Hortifruti com a categoria
-- Contrato: seq_produto, desc_produto, seq_familia, seq_categoria, nome_categoria
-- Regras:
--   * categoria pela FAMÍLIA, considerando só a ligação ATIVA (status = 'A');
--   * categoria no nível hierárquico configurado (:nivel_categoria);
--   * só as categorias do escopo -> não lê o cadastro inteiro de produtos.
-- A divisão vem das lojas: a ligação família x categoria é por divisão.
-- :categorias é expandido pelo ETL em :cat_0, :cat_1, ...
-- =============================================================================
SELECT DISTINCT
       p.seqproduto      AS seq_produto,
       p.desccompleta    AS desc_produto,
       p.seqfamilia      AS seq_familia,
       c.seqcategoria    AS seq_categoria,
       c.categoria       AS nome_categoria
  FROM map_produto p
  JOIN map_famdivcateg fc ON fc.seqfamilia   = p.seqfamilia
                         AND fc.status       = 'A'
  JOIN map_categoria c    ON c.seqcategoria  = fc.seqcategoria
                         AND c.nrodivisao    = fc.nrodivisao
                         AND c.nivelhierarquia = :nivel_categoria
 WHERE c.seqcategoria IN (:categorias)
   AND fc.nrodivisao IN (SELECT DISTINCT e.nrodivisao FROM max_empresa e)
