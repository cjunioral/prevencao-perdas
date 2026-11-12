# Descoberta na Consinco

Registro do que foi investigado no Oracle antes de escrever as extrações. Foram usadas só consultas
de leitura no dicionário de dados e em amostras pequenas, em horário comercial. Os scripts estão em
`sql/extracao/00_descoberta.sql` e de `09` a `12`.

Sem este registro, cada regra do ETL seria uma suposição. Aqui está a evidência por trás de cada uma.

## 1. Categorias

| Fato | Evidência | Efeito no ETL |
|---|---|---|
| Açougue = `SEQCATEGORIA 11`, Hortifruti = `24`, nível 1, divisão 1 (VAREJO) | `MAP_CATEGORIA` | `CATEGORIAS_ESCOPO=AÇOUGUE:11,HORTIFRUTI:24`, `NIVEL_CATEGORIA=1` |
| Há três árvores de categoria: `M` (16 categorias de nível 1), `C` (1) e `L` (1) | `MAP_CATEGORIA.TIPCATEGORIA` | Filtro `TIPCATEGORIA = 'M'` |
| Uma família pode ter ligação ativa nas três árvores ao mesmo tempo | `MAP_FAMDIVCATEG` com `STATUS = 'A'` | Sem o filtro, a mesma venda ou avaria seria contada até 3 vezes |
| A tela do ABC usa a árvore Mix | Parâmetro `TIPCATEGORIA=M` no rastro da tela | Mesmo critério nas consultas |

## 2. CGOs de avaria

| Fato | Evidência | Efeito no ETL |
|---|---|---|
| A marcação "ABC de movimentação" é `MAX_CODGERALOPER.INDFIXOABCMOVIMENTACAO = 'S'` (69 CGOs) | Dicionário de colunas | Filtro na `04_avarias.sql` |
| São do tipo avaria (`INDTIPOCGOMOVTO = 'AS'`): 549, 552, 562, 563 | `MAX_CODGERALOPER` | `CGOS_AVARIA=403,549,552,562,563` |
| 403 = transferência entre locais (entrada), exigido pelo enunciado | Idem | 403 só em local `T` |
| 563 = rendimento de produção | Idem | Incluído pela regra. Em set–out/2026 não teve lançamento no escopo: impacto zero |
| Tipos de local: A almoxarifado, D depósito, L loja, O refeitório, T troca | `MRL_LOCAL.TIPLOCAL` | 403 só em `T`, 552 só em `L` |
| Existe índice por data, CGO e empresa | `MRL_LANCTOESTOQIE5` | Filtro de data sem função na coluna, para usar o índice |

Amostra: um lançamento de R$ 17,7 mil no CGO 549 (loja 10, 15/09) era de "ALBUM FIFA WORLD CUP 2026",
fora do escopo. O filtro de categoria o exclui, como esperado.

## 3. Venda líquida

1. O SQL Monitor mostrou que a tela `frmAnlABCDistribSint` só grava parâmetros e lê o resultado em
   `MBIX_TABCSINTETICA`.
2. `MBIX_TABCSINTETICA` é uma tabela temporária de sessão (GTT), vazia para qualquer outra sessão. O
   cálculo roda numa procedure, e `ALL_SOURCE` não mostra o código ao usuário de leitura.
3. Então o SQL veio do próprio relatório, pelo **botão SQL** da tela (consulta 744454):
   base `MADMV_ABCDISTRIBPROD`, `VLRVENDALIQ = SUM(VLRITEM − VLRDEVOLITEM)`.
4. Conferência na loja 10, em 08/11/2026: tela R$ 352.775,08, lógica do ETL R$ 352.775,08, diferença
   **R$ 0,00**. Produtos (4.725) e quantidade (52.392,436) também iguais.

## 4. Regional

Nenhum cadastro de regional está preenchido:

| Objeto | Resultado |
|---|---|
| `MAX_EMPRESA` | Sem coluna de regional |
| `CT_REGIONAIS`, `CT_REGIONAISEMPRESAS` | Existem, 0 linhas |
| `MSUV_EMPRESASREGIAO`, `MAX_REGVDAEMP` | 0 linhas |
| `GE_CIDADE.REGIAO` | Vazia |
| `CONSINCOMONITOR.VW_REGIAO` | Vazia (é do monitor de PDV) |
| `NROSEGMENTOPRINC` / `MAD_SEGMENTO` | É canal de venda, não regional |

**Decisão:** a regra veio da área de negócio, em 11/11/2026: a lista de lojas por regional de
uma aplicação interna, revisada com a operação. São três regionais: **Mossoró, Natal e Paraíba**.

| Regional | Lojas |
|---|---|
| Mossoró | 1, 3, 6, 7, 8, 9, 10, 11, 26, 41 e 30 (Juazeiro do Norte, CE, "por enquanto") |
| Natal | 2, 12, 13, 14, 16, 19, 20, 22, 27, 42 |
| Paraíba | 4, 5, 15, 17, 18, 21, 23, 24, 25, 28, 40 |

* A regra **não é geográfica**: 019 (Assu) e 027 (Macau) são da Regional Natal. Por isso ela é
  aplicada por número da loja, e não por cidade ou UF.
* A lista da aplicação estava desatualizada: faltavam a 030 (que está na planilha de inventário),
  a 002, a 040 e a 042, incluídas na revisão.
* As outras empresas ativas (depósitos, estoques, operações que não são supermercado) ficam como
  `-1 SEM REGIONAL`: entram no total da rede, mas em nenhuma regional.
* Quando a regional for cadastrada na Consinco, muda só a `01_lojas.sql`.

## 5. Pendências com a área de negócio

1. ~~Qual é o agrupamento oficial de regionais?~~ Respondido pela operação em 11/11/2026 (acima).
2. ~~O CGO 563 (rendimento de produção) entra como avaria?~~ Sem lançamentos no escopo em set–out/2026 (verificado em 12/11): não muda o índice. Se passar a ter, a avaria aparece separada por CGO.
