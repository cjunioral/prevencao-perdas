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
| `controle.vw_rejeitado_vigente` | Linhas rejeitadas por motivo |

**Import ou DirectQuery?** Import. O volume é pequeno (milhares de linhas por mês),
o banco só muda uma vez por dia (06h00), e no Import o DAX roda no motor em
memória do Power BI: visuais rápidos e todas as funções de inteligência de tempo
disponíveis. DirectQuery só se justificaria com dado quase em tempo real ou
volume que não coubesse em memória — nenhum dos dois é o caso. Atualização: no
Desktop, *Atualizar* depois da carga; publicado, uma atualização agendada às
07h00 via gateway (depois da carga das 06h00).

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

## 3. Medidas DAX (crie uma tabela vazia `_Medidas` para organizá-las)

```DAX
Venda Líquida = SUM ( fato_venda[vlr_venda_liquida] )

Avaria Identificada = SUM ( fato_avaria[vlr_avaria] )

Perda Não Identificada = SUM ( fato_perda_inventario[vlr_falta] )
-- vlr_falta já aplica a regra: só faltas, em valor absoluto (sobras = 0)

Perda Total = [Avaria Identificada] + [Perda Não Identificada]

Índice de Perda = DIVIDE ( [Perda Total], [Venda Líquida] )
-- Razão das somas: em qualquer nível (loja, regional, rede) soma perdas e vendas
-- do contexto e divide. Nunca média de índices. DIVIDE evita erro sem venda.

% Perda Não Identificada = DIVIDE ( [Perda Não Identificada], [Perda Total] )

% Perda Identificada = DIVIDE ( [Avaria Identificada], [Perda Total] )

Índice Mês Anterior =
CALCULATE ( [Índice de Perda], DATEADD ( dim_data[data], -1, MONTH ) )

Variação Índice (p.p.) =
VAR atual = [Índice de Perda]
VAR anterior = [Índice Mês Anterior]
RETURN IF ( NOT ISBLANK ( atual ) && NOT ISBLANK ( anterior ), ( atual - anterior ) * 100 )
-- formato: 0,00 "p.p."

Índice Setembro =
CALCULATE ( [Índice de Perda], dim_data[ano_mes] = "2026-09" )

Índice Outubro =
CALCULATE ( [Índice de Perda], dim_data[ano_mes] = "2026-10" )

Variação Set → Out (p.p.) = ( [Índice Outubro] - [Índice Setembro] ) * 100

Ranking Loja =
IF (
    HASONEVALUE ( dim_loja[nome_loja] ),
    RANKX ( ALLSELECTED ( dim_loja[nome_loja] ), [Índice de Perda], , DESC, DENSE )
)

Ranking Regional =
IF (
    HASONEVALUE ( dim_regional[nome_regional] ),
    RANKX ( ALLSELECTED ( dim_regional[nome_regional] ), [Índice de Perda], , DESC, DENSE )
)

Última Carga OK = MAX ( vw_ultimo_sucesso[dt_ultima_carga_ok] )

Linhas Rejeitadas = COUNTROWS ( vw_rejeitado_vigente )
```

Formatos: índices e % em **Porcentagem com 2 casas**; valores em **R$** sem casas.

## 4. Páginas

**Filtros (painel lateral, sincronizados em todas as páginas):** Mês (`dim_data[mes_ano]`),
Regional, Loja, Categoria.

1. **Visão da rede**
   * Cartões: Venda Líquida, Perda Total, Índice de Perda, % Perda Não Identificada.
   * Colunas agrupadas: Índice de Perda por mês x categoria (setembro vs outubro).
   * Cartão: Variação Set → Out (p.p.), com cor condicional (piora em vermelho).
   * Colunas empilhadas 100%: Avaria Identificada vs Perda Não Identificada por categoria.
2. **Regionais e lojas**
   * Matriz: Regional > Loja nas linhas; Categoria nas colunas; valores Índice de Perda,
     Ranking Loja, Variação Set → Out (p.p.). Formatação condicional (escala) no índice.
   * Barras horizontais: Índice de Perda por loja, ordenado decrescente (top piores primeiro).
   * Dispersão (opcional): Venda Líquida (x) x Índice de Perda (y), tamanho = Perda Total.
3. **Qualidade dos dados**
   * Cartão: Última Carga OK (por fonte: tabela pequena com `fonte` e a data).
   * Barras: Linhas Rejeitadas por `descricao_motivo`, legenda `tipo_motivo`.
   * Tabela: rejeitados com aba, linha de origem, motivo e detalhe (para a área corrigir).

Na página de qualidade, desative a interação dos filtros de loja/categoria (rejeitados
não se ligam às dimensões).

## 5. Conferência antes de entregar

Compare os cartões do painel com `sql/analises/02_indice_regional.sql` (linha REDE):
venda, perdas e índice devem bater ao centavo. Se não baterem, quase sempre é
relacionamento faltando ou filtro de produto aplicado.
