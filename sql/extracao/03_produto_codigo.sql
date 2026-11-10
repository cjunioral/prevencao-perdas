-- =============================================================================
-- 03_produto_codigo.sql — códigos de barras (EAN) dos produtos do escopo
-- Usado para ligar a planilha à Consinco quando ela traz EAN em vez do
-- SEQPRODUTO. Contrato: cod_acesso, seq_produto, tip_codigo
-- =============================================================================
SELECT DISTINCT
       TO_CHAR(pc.codacesso)  AS cod_acesso,
       pc.seqproduto          AS seq_produto,
       pc.tipcodigo           AS tip_codigo
  FROM map_prodcodigo pc
  JOIN map_produto p      ON p.seqproduto   = pc.seqproduto
  JOIN map_famdivcateg fc ON fc.seqfamilia  = p.seqfamilia
                         AND fc.status      = 'A'
  JOIN map_categoria c    ON c.seqcategoria = fc.seqcategoria
                         AND c.nrodivisao   = fc.nrodivisao
                         AND c.nivelhierarquia = :nivel_categoria
                         AND c.tipcategoria = 'M'                  -- árvore mercadológica (há 3 árvores)
 WHERE c.seqcategoria IN (:categorias)
