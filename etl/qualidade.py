"""Funções puras de normalização dos campos da planilha.

Cada função devolve (valor, problema): valor convertido ou None, e o código do
motivo de rejeição quando não dá para converter. Também alimentam contadores
de "avisos" (tratamentos aplicados) para a tabela de qualidade do README.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

ERROS_EXCEL = {"#N/A", "#N/D", "#REF!", "#VALOR!", "#VALUE!", "#DIV/0!", "#NOME?", "#NAME?", "#NUM!", "#NULO!", "#NULL!"}
VAZIOS = {"", "-", "--", "N/A", "NA", "NULL", "NONE", "S/N", "?"}


def texto_normalizado(v: Any) -> str:
    """'  Açougue  ' -> 'ACOUGUE' (sem acento, maiúsculo, espaços simples)."""
    if v is None:
        return ""
    s = unicodedata.normalize("NFKD", str(v)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^\w/$%#!?.,\- ]", " ", s.upper())
    return re.sub(r"\s+", " ", s).strip()


def vazio(v: Any) -> bool:
    return v is None or (isinstance(v, str) and texto_normalizado(v) in VAZIOS)


def erro_excel(v: Any) -> bool:
    return isinstance(v, str) and v.strip().upper() in ERROS_EXCEL


# ----------------------------------------------------------------------------- valor
def parse_valor(v: Any, avisos: dict) -> tuple[Decimal | None, str | None]:
    """Aceita número, 'R$ -1.234,56', '(1.234,56)', '1.234,56-', '−12,5', '1234.56'."""
    if vazio(v):
        return None, "VALOR_AUSENTE"
    if erro_excel(v):
        return None, "VALOR_INVALIDO"
    if isinstance(v, bool):
        return None, "VALOR_INVALIDO"
    if isinstance(v, (int, float, Decimal)):
        return Decimal(str(v)).quantize(Decimal("0.01")), None

    s = str(v).strip().replace("−", "-").replace("\xa0", "").replace(" ", "")
    s = re.sub(r"(?i)R\$", "", s)
    negativo = False
    if s.startswith("(") and s.endswith(")"):
        negativo, s = True, s[1:-1]
        avisos["valor_formato_contabil"] = avisos.get("valor_formato_contabil", 0) + 1
    if s.endswith("-"):
        negativo, s = True, s[:-1]
    if s.startswith("-"):
        negativo, s = not negativo, s[1:]
    if "," in s and "." in s:                       # o último separador é o decimal
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):     # 1.234.567 -> milhar
        s = s.replace(".", "")
    try:
        d = Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None, "VALOR_INVALIDO"
    avisos["valor_texto_convertido"] = avisos.get("valor_texto_convertido", 0) + 1
    return (-d if negativo else d), None


# ----------------------------------------------------------------------------- data
FORMATOS_DATA = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y %H:%M:%S",
                 "%Y-%m-%d %H:%M:%S", "%d%m%Y")
RE_DATA = re.compile(r"\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2})\b")


def parse_data(v: Any, avisos: dict, minimo: date, maximo: date) -> tuple[date | None, str | None]:
    if vazio(v):
        return None, "DATA_AUSENTE"
    d: date | None = None
    if isinstance(v, datetime):
        d = v.date()
    elif isinstance(v, date):
        d = v
    elif isinstance(v, (int, float)) and 20000 < v < 80000:          # número serial do Excel
        d = date(1899, 12, 30) + timedelta(days=int(v))
        avisos["data_numero_serial"] = avisos.get("data_numero_serial", 0) + 1
    else:
        s = str(v).strip()
        m = RE_DATA.search(s)
        s = m.group(1) if m else s
        for fmt in FORMATOS_DATA:
            try:
                d = datetime.strptime(s, fmt).date()
                avisos["data_texto_convertida"] = avisos.get("data_texto_convertida", 0) + 1
                break
            except ValueError:
                continue
    if d is None or not (minimo <= d <= maximo):
        return None, "DATA_INVALIDA"
    return d, None


# ----------------------------------------------------------------------------- códigos
def parse_codigo(v: Any) -> str | None:
    """123 / 123.0 / ' 0123 ' / 7.89123E+12 -> '123' / '7891230000000' (só dígitos, sem zeros à esquerda)."""
    if vazio(v) or erro_excel(v):
        return None
    if isinstance(v, float):
        if not v.is_integer():
            return None
        v = int(v)
    s = str(v).strip()
    if re.fullmatch(r"\d+\.0+", s):
        s = s.split(".")[0]
    if re.fullmatch(r"\d+(\.\d+)?[eE]\+?\d+", s):                   # notação científica em texto
        s = str(int(Decimal(s)))
    s = re.sub(r"[\s.\-/]", "", s)
    if not s.isdigit():
        return None
    return s.lstrip("0") or None


RE_NUMERO_LOJA = re.compile(r"^\D{0,12}?(\d{1,4})\b")


def parse_loja(v: Any, nomes: dict[str, int]) -> tuple[int | None, str | None]:
    """5 / '005' / 'Loja 05' / 'L05 - Centro' / 'CENTRO' -> nº da empresa."""
    if vazio(v):
        return None, "LOJA_AUSENTE"
    if isinstance(v, (int, float)) and float(v).is_integer():
        return int(v), None
    s = texto_normalizado(v)
    if s in nomes:
        return nomes[s], None
    m = RE_NUMERO_LOJA.match(s)
    if m:
        return int(m.group(1)), None
    # 'LOJA CENTRO' contém 'CENTRO': só aceita se houver UM candidato (sem chute)
    candidatos = {nro for nome, nro in nomes.items() if nome and (nome in s or s in nome)}
    if len(candidatos) == 1:
        return candidatos.pop(), None
    return None, "LOJA_NAO_ENCONTRADA"
