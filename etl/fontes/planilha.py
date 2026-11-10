"""Leitura da planilha de inventário, que foi feita para leitura humana.

Não assume posição fixa de nada. Em vez disso:
  * localiza as abas pelo nome normalizado (sem acento/caixa/espaços extras);
  * encontra a linha de cabeçalho pontuando as primeiras linhas pelos nomes de
    coluna conhecidos (aceita cabeçalho em duas linhas, com célula mesclada);
  * identifica as colunas por sinônimos (Valor Divergente, Vlr. Diverg., ...);
  * propaga células mescladas (loja mesclada na vertical vale para o bloco);
  * reconhece linhas de contexto ("LOJA 05 - CENTRO", "Inventário 15/09/2026")
    que valem para as linhas de baixo;
  * classifica linhas que não são dado: em branco, total/subtotal, cabeçalho
    repetido;
  * detecta fórmula sem valor calculado (arquivo salvo fora do Excel).

Esta camada NÃO converte nem valida valores: só entrega cada linha com os
campos brutos. Conversão e cruzamento ficam em qualidade.py e carga_planilha.py.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import openpyxl

from ..qualidade import RE_DATA, texto_normalizado, vazio

log = logging.getLogger("planilha")

ABAS = {"AÇOUGUE": ("ACOUGUE",), "HORTIFRUTI": ("HORTI", "FLV")}


class ErroEstrutura(Exception):
    """A aba não tem a estrutura mínima (ex.: cabeçalho não encontrado)."""


def identificar_campo(t: str) -> str | None:
    if not t:
        return None
    tem = lambda *xs: any(x in t for x in xs)  # noqa: E731
    if tem("VALOR", "VLR", "R$") and tem("DIVERG", "DIFEREN"):
        return "valor"
    if tem("QTD", "QUANT") and tem("DIVERG", "DIFEREN"):
        return "qtd_divergente"
    if tem("QTD", "QUANT") and tem("CONGEL", "SISTEMA", "ESTOQUE"):
        return "qtd_sistema"
    if tem("EAN", "BARRA", "GTIN"):
        return "ean"
    if t in {"COD", "COD.", "CODIGO", "PLU", "SEQPRODUTO", "SEQ PRODUTO", "CODIGO INTERNO"} or \
       (t.startswith("COD") and not tem("LOJA", "FILIAL", "EMPRESA")):
        return "codigo"
    if tem("DESCRI") or t in {"PRODUTO", "ITEM", "NOME DO PRODUTO", "NOME PRODUTO", "MERCADORIA"}:
        return "descricao"
    if t.startswith(("LOJA", "FILIAL", "EMPRESA", "UNIDADE", "COD LOJA", "NRO LOJA")) or t in {"LJ", "LJ."}:
        return "loja"
    if t.startswith(("DATA", "DT")) or t in {"DIA"}:
        return "data"
    return None


@dataclass
class LinhaBruta:
    linha: int                                   # número da linha no Excel (1-based)
    campos: dict[str, Any]                       # loja, data, codigo, ean, descricao, valor
    original: dict[str, Any]                     # cabeçalho -> valor, como estava
    classificacao: str | None = None             # motivo, se não for linha de dado
    contexto_usado: list[str] = field(default_factory=list)


@dataclass
class AbaLida:
    rotulo: str
    nome_aba: str
    linha_cabecalho: int
    colunas: dict[str, str]                      # campo -> texto do cabeçalho
    linhas: list[LinhaBruta]
    avisos: dict[str, int]


def _json(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    return v


def localizar_abas(wb) -> tuple[dict[str, str], list[str]]:
    """Escolhe a aba de cada categoria. Regras (vindas da planilha real):
    * só abas VISÍVEIS: o arquivo traz dezenas de abas ocultas com histórico
      ("AÇOUGUE - JAN-25", "HORTI - MAI-25"...) em layout antigo; lê-las
      duplicaria ou misturaria dados;
    * entre as visíveis, prefere a que tem Tabela do Excel e o nome mais curto;
    * nome comparado sem acento/caixa e por trecho ("HORTIFRUTE" com erro de
      grafia ainda é reconhecida)."""
    achadas: dict[str, str] = {}
    ignoradas: list[str] = []
    for rotulo, chaves in ABAS.items():
        cands = [n for n in wb.sheetnames if any(c in texto_normalizado(n) for c in chaves)]
        visiveis = [n for n in cands if wb[n].sheet_state == "visible"]
        ignoradas += [n for n in cands if n not in visiveis]
        if visiveis:
            visiveis.sort(key=lambda n: (not wb[n].tables, len(n)))
            achadas[rotulo] = visiveis[0]
            if len(visiveis) > 1:
                log.warning("Mais de uma aba VISÍVEL para %s: usando '%s', ignorando %s — confira se não há "
                            "dados novos nelas", rotulo, visiveis[0], visiveis[1:])
                ignoradas += visiveis[1:]
    return achadas, ignoradas


def _grade(ws) -> list[list[Any]]:
    grade = [list(r) for r in ws.iter_rows(values_only=True)]
    largura = max((len(r) for r in grade), default=0)
    for r in grade:
        r.extend([None] * (largura - len(r)))
    for rng in ws.merged_cells.ranges:                       # propaga mescladas
        v = ws.cell(rng.min_row, rng.min_col).value
        for lin in range(rng.min_row, rng.max_row + 1):
            for col in range(rng.min_col, rng.max_col + 1):
                if lin - 1 < len(grade) and col - 1 < largura:
                    grade[lin - 1][col - 1] = v
    return grade


def _achar_cabecalho(grade: list[list[Any]]) -> tuple[int, dict[int, str], dict[str, str]]:
    melhor = (-1, 0, {}, {})
    for i, linha in enumerate(grade[:40]):
        anterior = grade[i - 1] if i > 0 else [None] * len(linha)
        mapa, textos = {}, {}
        for j, v in enumerate(linha):
            t = texto_normalizado(v)
            campo = identificar_campo(t)
            if campo is None and anterior[j] is not None and not isinstance(v, (int, float)):
                t = texto_normalizado(f"{anterior[j]} {v or ''}")   # cabeçalho em 2 linhas
                campo = identificar_campo(t)
            if campo and campo not in textos:
                mapa[j], textos[campo] = campo, str(v if v is not None else anterior[j]).strip()
        pontos = len(textos)
        if "valor" in textos and ({"codigo", "ean"} & textos.keys()) and pontos > melhor[1]:
            melhor = (i, pontos, mapa, textos)
    if melhor[0] < 0:
        raise ErroEstrutura("cabeçalho não encontrado (precisa de colunas de código do produto e valor divergente)")
    return melhor[0], melhor[2], melhor[3]


def ler_aba(wb_valores, wb_formulas, rotulo: str, nome_aba: str) -> AbaLida:
    ws, wsf = wb_valores[nome_aba], wb_formulas[nome_aba]
    avisos: dict[str, int] = {}
    soma = lambda k, n=1: avisos.__setitem__(k, avisos.get(k, 0) + n)  # noqa: E731

    if ws.merged_cells.ranges:
        soma("intervalos_mesclados_propagados", len(ws.merged_cells.ranges))
    grade = _grade(ws)
    i_cab, mapa, textos = _achar_cabecalho(grade)
    if i_cab > 0:
        soma("linhas_de_titulo_antes_do_cabecalho", i_cab)
    cab_textos = {texto_normalizado(v) for v in grade[i_cab] if v is not None}
    nomes_colunas = [str(v).strip() if v is not None else f"col_{j + 1}" for j, v in enumerate(grade[i_cab])]
    com_cabecalho = [j for j, v in enumerate(grade[i_cab]) if v is not None]

    j_val = next(j for j, c in mapa.items() if c == "valor")

    # contexto vindo do título (ex.: "Loja 05 - Inventário 15/09/2026")
    ctx: dict[str, Any] = {}
    for linha in grade[:i_cab]:
        _contexto(linha, ctx)

    linhas: list[LinhaBruta] = []
    for i in range(i_cab + 1, len(grade)):
        bruto = grade[i]
        nlin = i + 1
        if all(vazio(bruto[j]) for j in com_cabecalho):
            soma("linhas_em_branco_ignoradas")
            continue
        if ws.row_dimensions[nlin].hidden:
            soma("linhas_ocultas_lidas")
        campos = {campo: bruto[j] for j, campo in mapa.items()}
        original = {nomes_colunas[j]: _json(bruto[j]) for j in com_cabecalho if bruto[j] is not None}

        textos_linha = [texto_normalizado(v) for v in bruto if not vazio(v)]
        lb = LinhaBruta(nlin, campos, original)
        if sum(1 for t in textos_linha if t in cab_textos) >= 2:
            lb.classificacao = "CABECALHO_REPETIDO"
        elif any(t.startswith(("TOTAL", "SUBTOTAL", "SOMA ", "TOT.")) for t in textos_linha if not t[:1].isdigit()):
            lb.classificacao = "LINHA_TOTALIZADORA"
        elif len(textos_linha) <= 2 and vazio(campos.get("valor")) and vazio(campos.get("codigo")) \
                and vazio(campos.get("ean")) and _contexto(bruto, ctx):
            soma("linhas_de_contexto")
            continue                                   # não é dado: define loja/data das próximas
        elif all(vazio(campos.get(k)) for k in ("loja", "data", "codigo", "ean", "valor", "descricao")):
            lb.classificacao = "LINHA_SEM_DADOS"
        else:
            qs = campos.get("qtd_sistema")
            if isinstance(qs, (int, float)) and qs < 0:
                soma("estoque_sistema_negativo")
            # fórmula sem valor em cache -> o Excel nunca calculou (arquivo salvo por outra ferramenta)
            fv = wsf.cell(nlin, j_val + 1).value
            if campos.get("valor") is None and isinstance(fv, str) and fv.startswith("="):
                soma("formula_sem_valor_calculado")
                original["_formula_valor"] = fv
            for campo in ("loja", "data"):
                if vazio(campos.get(campo)) and ctx.get(campo) is not None:
                    campos[campo] = ctx[campo]
                    lb.contexto_usado.append(campo)
            if lb.contexto_usado:
                soma("loja_ou_data_herdada_do_bloco")
        linhas.append(lb)

    faltando = {"loja", "data"} - textos.keys()
    if faltando:
        soma("coluna_ausente_" + "_".join(sorted(faltando)))
    log.info("Aba '%s': cabeçalho na linha %d, colunas %s, %d linhas candidatas",
             nome_aba, i_cab + 1, textos, len(linhas))
    return AbaLida(rotulo, nome_aba, i_cab + 1, textos, linhas, avisos)


def _contexto(linha: list[Any], ctx: dict[str, Any]) -> bool:
    """Linha tipo 'LOJA: 05 - CENTRO' ou 'Data do inventário: 15/09/2026'."""
    achou = False
    for v in linha:
        if vazio(v):
            continue
        if isinstance(v, (datetime, date)):
            ctx["data"], achou = v, True
            continue
        t = texto_normalizado(v)
        if t.startswith(("LOJA", "FILIAL")):
            ctx["loja"], achou = t, True
        m = RE_DATA.search(str(v))
        if m and ("INVENT" in t or "DATA" in t or "CONTAGEM" in t):
            ctx["data"], achou = m.group(1), True
    return achou


def abrir(caminho: Path):
    """Abre duas vezes: valores calculados e fórmulas (para detectar cache vazio)."""
    valores = openpyxl.load_workbook(caminho, data_only=True, keep_vba=False)
    formulas = openpyxl.load_workbook(caminho, data_only=False, keep_vba=False)
    return valores, formulas
