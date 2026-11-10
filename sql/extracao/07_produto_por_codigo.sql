-- =============================================================================
-- 07_produto_por_codigo.sql — diagnóstico dos códigos da planilha sem par
-- Chamado pelo ETL só para os poucos códigos que não casaram com os produtos
-- do escopo. Diferencia "produto não existe" de "produto existe, mas é de outra
-- categoria" (motivos de rejeição diferentes, ações diferentes para a área).
-- Contrato: seq_produto, desc_produto
-- :codigos é expandido pelo ETL em :cod_0, :cod_1, ... (blocos de até 500)
-- =============================================================================
SELECT p.seqproduto   AS seq_produto,
       p.desccompleta AS desc_produto
  FROM map_produto p
 WHERE p.seqproduto IN (:codigos)
