# Consultas do Power Query (código M versionado)

O `.pbix` não vai para o Git (contém dados importados). Este arquivo guarda o código M de
todas as consultas, para revisão e para recriar o painel do zero.

**Boas práticas aplicadas**
* Parâmetros `pServidor`/`pBanco`: trocar de ambiente (teste → produção) em um campo só.
* Consulta `Banco` única, não carregada: a conexão fica em um lugar.
* `CreateNavigationProperties = false`: sem colunas de navegação `[Table]` inúteis.
* Seleção explícita de colunas: só o que o painel usa.
* Tipos explícitos; valores em Decimal Fixo (`Currency.Type`): sem erro de ponto flutuante.
* Query folding preservado nas tabelas grandes (seleção e tipos viram SQL no PostgreSQL).
* Fuso horário resolvido **no banco**: as views de controle já entregam a hora de Brasília (`AT TIME ZONE`).
  O conector de PostgreSQL trata `timestamptz` de forma ambígua; transformar perto da fonte evita isso.
* Grupos: Parâmetros, Conexão, Dimensões, Fatos, Controle.

---

## Passo a passo no Editor do Power Query

Ponto de partida: as consultas que vieram do Navegador (`analitico dim_data`, ...).

### Etapa A — Parâmetros
1. **Página Inicial → Gerenciar Parâmetros → Novo Parâmetro.**
2. Nome `pServidor` · Obrigatório ✔ · Tipo **Texto** · Valores sugeridos **Qualquer valor** · Valor atual `localhost` → **OK**.
3. Repita: Nome `pBanco` · Obrigatório ✔ · Tipo **Texto** · Valor atual `prevencao_perdas_teste` → **OK**.

### Etapa B — Consulta `Banco`
1. **Página Inicial → Nova Fonte → Consulta Nula** (último item da lista).
2. No painel da direita (Propriedades → Nome), troque `Consulta1` por `Banco`.
3. **Página Inicial → Editor Avançado** → apague tudo → cole o código **B** abaixo → **Concluído**.
4. Clique com o botão direito em `Banco` na lista à esquerda → **desmarque "Habilitar carregamento"**.

### Etapa D — As consultas que já existem (repita para cada uma)
1. Clique na consulta na lista à esquerda (ex.: `analitico dim_data`).
2. **Editor Avançado** → apague tudo → cole o código da tabela correspondente → **Concluído**.
3. Renomeie tirando o prefixo do schema (ex.: `dim_data`).
4. Confira que as colunas `[Table]` sumiram e que nenhuma coluna mostra `Error`.

| Consulta que veio do Navegador | Novo nome | Código |
|---|---|---|
| `analitico dim_data` | `dim_data` | D1 |
| `analitico dim_regional` | `dim_regional` | D2 |
| `analitico dim_loja` | `dim_loja` | D3 |
| `analitico dim_categoria` | `dim_categoria` | D4 |
| `analitico dim_produto` | `dim_produto` | D5 |
| `analitico fato_venda` | `fato_venda` | D6 |
| `analitico fato_avaria` | `fato_avaria` | D7 |
| `analitico fato_perda_inventario` | `fato_perda_inventario` | D8 |
| `controle vw_ultimo_sucesso` | `vw_ultimo_sucesso` | D9 |
| `controle vw_ultima_carga` | `vw_ultima_carga` | D10 |

### Etapa E — Consulta nova `vw_rejeitado_vigente`
1. **Nova Fonte → Consulta Nula** → renomeie para `vw_rejeitado_vigente`.
2. **Editor Avançado** → cole o código **E** → **Concluído**.

### Etapa F — Organizar em grupos
Botão direito na consulta → **Mover para o Grupo → Novo Grupo...** (depois, para as outras, escolha o grupo já criado):

| Grupo | Consultas |
|---|---|
| `1 Parâmetros` | `pServidor`, `pBanco` |
| `2 Conexão` | `Banco` |
| `3 Dimensões` | `dim_data`, `dim_regional`, `dim_loja`, `dim_categoria`, `dim_produto` |
| `4 Fatos` | `fato_venda`, `fato_avaria`, `fato_perda_inventario` |
| `5 Controle` | `vw_ultimo_sucesso`, `vw_ultima_carga`, `vw_rejeitado_vigente` |

### Etapa G — Checagens antes de aplicar
1. **Query folding:** em `fato_venda`, botão direito no último passo (`Tipos`) → **Exibir Consulta Nativa**
   deve estar habilitado e mostrar um `select ... from "analitico"."fato_venda"`.
2. **Carregamento:** `pServidor`, `pBanco` e `Banco` aparecem em *itálico* (não carregam).
3. **Página Inicial → Fechar e Aplicar.**

### Trocar para o banco real
**Página Inicial (Power BI) → Transformar dados ▾ → Editar parâmetros** → `pBanco = prevencao_perdas` → **OK** → **Aplicar alterações**.

---

## Códigos

### B · `Banco`
```m
// Conexão única com o banco analítico. Não é carregada no modelo:
// as demais consultas a referenciam. Trocar de ambiente = mudar pBanco.
let
    Fonte = PostgreSQL.Database(pServidor, pBanco, [CreateNavigationProperties = false])
in
    Fonte
```

### D1 · `dim_data`
```m
// Calendário (2024–2028), gerado no banco. Marcar como tabela de datas no modelo.
let
    Fonte   = Banco,
    Tabela  = Fonte{[Schema = "analitico", Item = "dim_data"]}[Data],
    Colunas = Table.SelectColumns(Tabela, {
                "data", "ano", "mes", "ano_mes", "nome_mes", "mes_ano",
                "inicio_mes", "trimestre", "dia", "dia_semana", "nome_dia"}),
    Tipos   = Table.TransformColumnTypes(Colunas, {
                {"data", type date}, {"ano", Int64.Type}, {"mes", Int64.Type},
                {"ano_mes", type text}, {"nome_mes", type text}, {"mes_ano", type text},
                {"inicio_mes", type date}, {"trimestre", Int64.Type}, {"dia", Int64.Type},
                {"dia_semana", Int64.Type}, {"nome_dia", type text}})
in
    Tipos
```

### D2 · `dim_regional`
```m
let
    Fonte   = Banco,
    Tabela  = Fonte{[Schema = "analitico", Item = "dim_regional"]}[Data],
    Colunas = Table.SelectColumns(Tabela, {"nro_regional", "nome_regional"}),
    Tipos   = Table.TransformColumnTypes(Colunas, {
                {"nro_regional", Int64.Type}, {"nome_regional", type text}})
in
    Tipos
```

### D3 · `dim_loja`
```m
// loja_rotulo ("005 - HQ PATOS") garante nome único nos visuais. O ideal seria
// criá-lo numa view no banco (transformar o mais perto da fonte); aqui é uma
// tabela pequena, custo desprezível.
let
    Fonte   = Banco,
    Tabela  = Fonte{[Schema = "analitico", Item = "dim_loja"]}[Data],
    Colunas = Table.SelectColumns(Tabela, {
                "nro_empresa", "nome_loja", "nro_regional", "cidade", "uf", "ativa"}),
    Tipos   = Table.TransformColumnTypes(Colunas, {
                {"nro_empresa", Int64.Type}, {"nome_loja", type text},
                {"nro_regional", Int64.Type}, {"cidade", type text},
                {"uf", type text}, {"ativa", type logical}}),
    Rotulo  = Table.AddColumn(Tipos, "loja_rotulo",
                each Text.PadStart(Text.From([nro_empresa]), 3, "0") & " - " & [nome_loja],
                type text)
in
    Rotulo
```

### D4 · `dim_categoria`
```m
let
    Fonte   = Banco,
    Tabela  = Fonte{[Schema = "analitico", Item = "dim_categoria"]}[Data],
    Colunas = Table.SelectColumns(Tabela, {"seq_categoria", "nome_categoria", "categoria"}),
    Tipos   = Table.TransformColumnTypes(Colunas, {
                {"seq_categoria", Int64.Type}, {"nome_categoria", type text},
                {"categoria", type text}})
in
    Tipos
```

### D5 · `dim_produto`
```m
// Sem relacionamento com dim_categoria no modelo (evita caminho ambíguo):
// a categoria chega aos fatos direto por seq_categoria.
let
    Fonte   = Banco,
    Tabela  = Fonte{[Schema = "analitico", Item = "dim_produto"]}[Data],
    Colunas = Table.SelectColumns(Tabela, {"seq_produto", "desc_produto", "seq_familia"}),
    Tipos   = Table.TransformColumnTypes(Colunas, {
                {"seq_produto", Int64.Type}, {"desc_produto", type text},
                {"seq_familia", Int64.Type}})
in
    Tipos
```

### D6 · `fato_venda`
```m
// Grão: loja x categoria x dia. Valores em Decimal Fixo (moeda).
let
    Fonte   = Banco,
    Tabela  = Fonte{[Schema = "analitico", Item = "fato_venda"]}[Data],
    Colunas = Table.SelectColumns(Tabela, {
                "nro_empresa", "seq_categoria", "data",
                "vlr_venda_bruta", "vlr_devolucao", "vlr_venda_liquida"}),
    Tipos   = Table.TransformColumnTypes(Colunas, {
                {"nro_empresa", Int64.Type}, {"seq_categoria", Int64.Type}, {"data", type date},
                {"vlr_venda_bruta", Currency.Type}, {"vlr_devolucao", Currency.Type},
                {"vlr_venda_liquida", Currency.Type}})
in
    Tipos
```

### D7 · `fato_avaria`
```m
// Grão: loja x produto x dia x CGO.
let
    Fonte   = Banco,
    Tabela  = Fonte{[Schema = "analitico", Item = "fato_avaria"]}[Data],
    Colunas = Table.SelectColumns(Tabela, {
                "nro_empresa", "seq_produto", "data", "cgo", "seq_categoria",
                "qtd_lancada", "vlr_avaria"}),
    Tipos   = Table.TransformColumnTypes(Colunas, {
                {"nro_empresa", Int64.Type}, {"seq_produto", Int64.Type}, {"data", type date},
                {"cgo", Int64.Type}, {"seq_categoria", Int64.Type},
                {"qtd_lancada", type number}, {"vlr_avaria", Currency.Type}})
in
    Tipos
```

### D8 · `fato_perda_inventario`
```m
// vlr_falta já aplica a regra de negócio no banco (só faltas, valor absoluto).
// aba_origem + linha_origem rastreiam qualquer número até a linha do Excel.
let
    Fonte   = Banco,
    Tabela  = Fonte{[Schema = "analitico", Item = "fato_perda_inventario"]}[Data],
    Colunas = Table.SelectColumns(Tabela, {
                "nro_empresa", "seq_produto", "data", "seq_categoria",
                "vlr_divergente", "vlr_falta", "aba_origem", "linha_origem"}),
    Tipos   = Table.TransformColumnTypes(Colunas, {
                {"nro_empresa", Int64.Type}, {"seq_produto", Int64.Type}, {"data", type date},
                {"seq_categoria", Int64.Type}, {"vlr_divergente", Currency.Type},
                {"vlr_falta", Currency.Type}, {"aba_origem", type text},
                {"linha_origem", Int64.Type}})
in
    Tipos
```

### D9 · `vw_ultimo_sucesso`
```m
// Data da última carga bem-sucedida por fonte ("atualizado até quando?").
let
    Fonte   = Banco,
    Tabela  = Fonte{[Schema = "controle", Item = "vw_ultimo_sucesso"]}[Data],
    Colunas = Table.SelectColumns(Tabela, {"fonte", "dt_ultima_carga_ok"}),
    // a view já entrega a hora de Brasília (sem fuso)
    Tipos   = Table.TransformColumnTypes(Colunas, {
                {"fonte", type text}, {"dt_ultima_carga_ok", type datetime}})
in
    Tipos
```

### D10 · `vw_ultima_carga`
```m
// Status da última carga de cada fonte/aba: lidas, carregadas, rejeitadas e o
// efeito no analítico (+ inseridas, ~ atualizadas, − removidas).
let
    Fonte   = Banco,
    Tabela  = Fonte{[Schema = "controle", Item = "vw_ultima_carga"]}[Data],
    Colunas = Table.SelectColumns(Tabela, {
                "fonte", "aba", "arquivo", "status", "periodo_inicio", "periodo_fim",
                "inicio", "fim", "linhas_lidas", "linhas_carregadas", "linhas_rejeitadas",
                "linhas_inseridas", "linhas_atualizadas", "linhas_removidas", "mensagem"}),
    // inicio/fim já vêm no horário de Brasília (conversão feita na view)
    Tipos   = Table.TransformColumnTypes(Colunas, {
                {"fonte", type text}, {"aba", type text}, {"arquivo", type text},
                {"status", type text}, {"periodo_inicio", type date}, {"periodo_fim", type date},
                {"inicio", type datetime}, {"fim", type datetime},
                {"linhas_lidas", Int64.Type}, {"linhas_carregadas", Int64.Type},
                {"linhas_rejeitadas", Int64.Type}, {"linhas_inseridas", Int64.Type},
                {"linhas_atualizadas", Int64.Type}, {"linhas_removidas", Int64.Type},
                {"mensagem", type text}})
in
    Tipos
```

### E · `vw_rejeitado_vigente`
```m
// Linhas rejeitadas da última carga de cada fonte/aba, com motivo, tipo e detalhe.
// registro_original = a linha como veio da planilha (JSON), para a área corrigir.
let
    Fonte   = Banco,
    Tabela  = Fonte{[Schema = "controle", Item = "vw_rejeitado_vigente"]}[Data],
    Colunas = Table.SelectColumns(Tabela, {
                "id_rejeitado", "fonte", "aba", "linha_origem", "motivo", "tipo_motivo",
                "descricao_motivo", "detalhe", "registro_original", "dt_registro"}),
    // dt_registro já vem no horário de Brasília (conversão feita na view)
    Tipos   = Table.TransformColumnTypes(Colunas, {
                {"id_rejeitado", Int64.Type}, {"fonte", type text}, {"aba", type text},
                {"linha_origem", Int64.Type}, {"motivo", type text}, {"tipo_motivo", type text},
                {"descricao_motivo", type text}, {"detalhe", type text},
                {"registro_original", type text}, {"dt_registro", type datetime}})
in
    Tipos
```
