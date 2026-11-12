# Painel Power BI — montagem passo a passo

O `.pbix` é montado no Power BI Desktop (Windows). Este roteiro garante que as
medidas e o modelo fiquem consistentes com o banco.

## 1. Conexão (direto no banco, sem planilha/CSV no meio)

1. **Obter dados → Banco de dados PostgreSQL**. Servidor `localhost:5432`, banco `prevencao_perdas`.
2. Modo de conectividade: **Importar** (justificativa abaixo).
3. Credenciais: aba *Banco de dados*, usuário somente leitura (papel `leitura_bi`, ver `sql/ddl/07_permissoes.sql`).
   Se der erro de SSL no PostgreSQL local, desmarque *Criptografar conexões* nas configurações da fonte.
4. Selecione as tabelas/views:

| Objeto | Papel no modelo |
|---|---|
| `analitico.dim_data` | Dimensão data (marcar como tabela de datas, coluna `data`) |
| `analitico.dim_loja` | Dimensão loja |
| `analitico.dim_regional` | Dimensão regional |
| `analitico.dim_categoria` | Dimensão categoria |
| `analitico.dim_produto` | Dimensão produto (detalhe de avaria/inventário) |
| `analitico.fato_avaria` | Fato: avaria identificada |
| `analitico.fato_venda` | Fato: venda líquida |
| `analitico.fato_perda_inventario` | Fato: perda não identificada |
| `controle.vw_ultimo_sucesso` | Data da última carga por fonte |
| `controle.vw_ultima_carga` | Status e contagens da última carga de cada fonte/aba |
| `controle.vw_rejeitado_vigente` | Linhas rejeitadas por motivo |

**Import ou DirectQuery?** Import. O volume é pequeno (milhares de linhas por mês),
o banco só muda uma vez por dia (06h00), e no Import o DAX roda no motor em
memória do Power BI: visuais rápidos e todas as funções de inteligência de tempo
disponíveis. DirectQuery só se justificaria com dado quase em tempo real ou
volume que não coubesse em memória — nenhum dos dois é o caso. Atualização: no
Desktop, *Atualizar* depois da carga; publicado, uma atualização agendada às
06h30 via gateway (depois da carga das 06h00, antes de a loja abrir).

**Parâmetros:** `pServidor` e `pBanco` (obrigatórios). O repositório guarda o
modelo `painel_prevencao_perdas.pbit`, sem dados: ao abrir, ele pede os dois
parâmetros e carrega do banco de quem abriu. O `.pbix`, que contém dados reais,
não vai para o Git.

## 2. Relacionamentos (esquema estrela, 1:N, filtro em direção única)

```
dim_data[data]                 1 ── N  fato_venda[data], fato_avaria[data], fato_perda_inventario[data]
dim_loja[nro_empresa]          1 ── N  fato_venda, fato_avaria, fato_perda_inventario
dim_categoria[seq_categoria]   1 ── N  fato_venda, fato_avaria, fato_perda_inventario
dim_produto[seq_produto]       1 ── N  fato_avaria, fato_perda_inventario
dim_regional[nro_regional]     1 ── N  dim_loja[nro_regional]
```

* `fato_venda` não tem produto (o grão é loja x categoria x dia). Por isso o
  índice só deve ser filtrado por loja, regional, categoria e data — **não** use
  `dim_produto` como filtro de página (a venda não reagiria e o índice ficaria errado).
* Oculte as colunas-chave das tabelas fato (o usuário filtra pelas dimensões).
* `dim_data`: classifique `mes_ano` pela coluna `ano_mes`.

## 3. Medidas DAX (tabela vazia `_Medidas`, organizada em pastas de exibição)

A pasta de exibição é definida em *Exibição de modelo > Propriedades > Pasta de exibição*.

### Regra do índice

O índice só existe onde a loja fez inventário da categoria no mês. Sem inventário,
a perda não identificada é **desconhecida**, não zero: somar essa venda e essa
avaria puxaria o índice para baixo (em set/2026, o Açougue cairia de 3,10% para
2,05%). As medidas "Base do Índice" restringem o cálculo às combinações
loja x categoria x mês com inventário; a **Cobertura** mostra quanto da venda
ficou dentro.

### 1 Valores (Moeda, 0 casas)

```DAX
Venda Líquida = SUM ( fato_venda[vlr_venda_liquida] )
Avaria Identificada = SUM ( fato_avaria[vlr_avaria] )
Perda Não Identificada = SUM ( fato_perda_inventario[vlr_falta] )
Perda Total = [Avaria Identificada] + [Perda Não Identificada]

Venda Base do Índice =
CALCULATE (
    [Venda Líquida],
    FILTER (
        CROSSJOIN (
            VALUES ( dim_loja[nro_empresa] ),
            VALUES ( dim_categoria[seq_categoria] ),
            VALUES ( dim_data[ano_mes] )
        ),
        CALCULATE ( COUNTROWS ( fato_perda_inventario ) ) > 0
    )
)
-- Avaria Base do Índice e Perda Base do Índice: a mesma fórmula, trocando
-- [Venda Líquida] por [Avaria Identificada] e por [Perda Total].
```

### 2 Índices (Porcentagem, 2 casas; cobertura com 1)

```DAX
Índice de Perda = DIVIDE ( [Perda Base do Índice], [Venda Base do Índice] )
-- razão das somas em qualquer nível (loja, regional, rede); nunca média de índices

% Perda Não Identificada = DIVIDE ( [Perda Não Identificada], [Perda Base do Índice] )
% Perda Identificada      = DIVIDE ( [Avaria Base do Índice], [Perda Base do Índice] )
Cobertura do Inventário   = DIVIDE ( [Venda Base do Índice], [Venda Líquida] )

Índice da Rede =
CALCULATE ( [Índice de Perda], REMOVEFILTERS ( dim_loja ), REMOVEFILTERS ( dim_regional ) )
-- mantém categoria e mês: é a régua de "acima da rede" das cores

Índice Açougue    = CALCULATE ( [Índice de Perda], KEEPFILTERS ( dim_categoria[categoria] = "AÇOUGUE" ) )
Índice Hortifruti = CALCULATE ( [Índice de Perda], KEEPFILTERS ( dim_categoria[categoria] = "HORTIFRUTI" ) )
```

### 3 Comparação

```DAX
Índice Mês Anterior = CALCULATE ( [Índice de Perda], DATEADD ( dim_data[data], -1, MONTH ) )
Índice Setembro     = CALCULATE ( [Índice de Perda], dim_data[ano_mes] = "2026-09" )
Índice Outubro      = CALCULATE ( [Índice de Perda], dim_data[ano_mes] = "2026-10" )

Variação Set → Out (p.p.) =            -- formato 0.00 "p.p."
VAR setembro = [Índice Setembro]
VAR outubro  = [Índice Outubro]
RETURN
    IF ( NOT ISBLANK ( setembro ) && NOT ISBLANK ( outubro ), ( outubro - setembro ) * 100 )
-- em branco até existir inventário nos dois meses (não vira "-3,10 p.p.")
```

### 4 Ranking

```DAX
Ranking Loja =
IF ( HASONEVALUE ( dim_loja[nome_loja] ),
     RANKX ( ALLSELECTED ( dim_loja[nome_loja] ), [Índice de Perda], , DESC, DENSE ) )
Ranking Regional =
IF ( HASONEVALUE ( dim_regional[nome_regional] ),
     RANKX ( ALLSELECTED ( dim_regional[nome_regional] ), [Índice de Perda], , DESC, DENSE ) )
```

### 5 Qualidade

```DAX
Dados Atualizados Até    = MAX ( vw_ultimo_sucesso[dt_ultima_carga_ok] )   -- dd/mm/yyyy hh:nn
Linhas Rejeitadas        = COUNTROWS ( vw_rejeitado_vigente )
Fontes com Sucesso       = CALCULATE ( COUNTROWS ( vw_ultima_carga ), vw_ultima_carga[status] = "SUCESSO" )
Fontes na Última Carga   = COUNTROWS ( vw_ultima_carga )
Fontes OK                = FORMAT ( [Fontes com Sucesso], "0" ) & " de " & FORMAT ( [Fontes na Última Carga], "0" )
Linhas Lidas da Planilha =
    CALCULATE ( SUM ( vw_ultima_carga[linhas_lidas] ), vw_ultima_carga[fonte] = "planilha_inventario" )
% Planilha Rejeitada =
    DIVIDE ( CALCULATE ( [Linhas Rejeitadas], vw_rejeitado_vigente[fonte] = "planilha_inventario" ),
             [Linhas Lidas da Planilha] )
Cobertura Setembro = CALCULATE ( [Cobertura do Inventário], dim_data[ano_mes] = "2026-09" )
```

### 6 Formatação (só para formatar visuais)

```DAX
Cor do Índice  = IF ( [Índice de Perda] > [Índice da Rede], "#E60D25", "#333333" )
Cor do Status  = SWITCH ( SELECTEDVALUE ( vw_ultima_carga[status] ),
                          "SUCESSO", "#2E7D32", "FALHA", "#B00A1C", "#605E5C" )
Cor Fontes OK  = IF ( [Fontes com Sucesso] = [Fontes na Última Carga], "#2E7D32", "#B00A1C" )
Aviso Outubro  =
IF ( ISBLANK ( [Índice Outubro] ),
     "Outubro sem inventário carregado: o índice aparece quando a planilha de outubro chegar.",
     "Set × out com inventário nas duas pontas." )
```

## 4. Páginas (1920 x 1080, tema `tema_grupo_queiroz.json`)

Todas têm o mesmo topo (título, fórmula, "Atualizado em") e um painel lateral com
os filtros e um bloco "Como ler". Filtro de página em todas: `ano_mes` = set e out/2026.
Os segmentadores de mês, regional, loja e categoria são sincronizados entre as
páginas 1 e 2.

| Página | Pergunta | Visuais |
|---|---|---|
| **Visão da rede** | Quanto perdemos? | Cartão com venda e perda (base do índice), índice, % não identificada e cobertura; colunas do índice set × out por categoria (subtítulo "Aviso Outubro"); colunas 100% da composição identificada × não identificada |
| **Regionais e lojas** | Onde está a perda? | Índice por regional em pequenos múltiplos por categoria (vermelho = acima da rede na categoria); placar das regionais; matriz regional → loja com gradiente por categoria; top 10 lojas (N superior pelo índice) |
| **Qualidade e carga** | Dá para confiar? | Fontes com sucesso, linhas rejeitadas, % da planilha rejeitada, cobertura de setembro; status da última carga de cada fonte; rejeições por motivo; lista das linhas rejeitadas com aba, linha do Excel e detalhe |
| Conferência (oculta) | Bate com o SQL? | Tabela para comparar com `sql/analises/02_indice_regional.sql` |

Formatação condicional:
* índice: fundo em gradiente branco → `#F7B5BC`, uma escala por categoria na matriz;
* % não identificada ≥ 70%: fonte `#B00A1C` (régua da análise 03);
* cobertura < 62%: fonte `#B00A1C`;
* status da carga e "Fontes com sucesso": cor pela medida (verde/vermelho);
* barras de regional e loja: `Cor do Índice`.

## 5. Conferência antes de entregar

Com set/2026 e sem outros filtros, o painel deve mostrar o mesmo que
`sql/analises/02_indice_regional.sql`:

| Recorte | Índice |
|---|---:|
| Rede (Açougue + Hortifruti) | 4,78% |
| Rede · Açougue | 3,10% |
| Rede · Hortifruti | 8,65% |
| Natal · Açougue | 3,71% |
| Mossoró · Hortifruti | 10,04% |
