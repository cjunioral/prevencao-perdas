"""Gera dados FICTÍCIOS para testar o ETL sem acesso à produção.

    python tests/gerar_dados_ficticios.py            # CSVs da Consinco + planilha até setembro
    python tests/gerar_dados_ficticios.py --outubro  # planilha atualizada até outubro

A planilha reproduz de propósito os problemas típicos de arquivo feito para
leitura humana (títulos, mesclas, totais, textos no lugar de números, datas
em vários formatos, duplicidades, códigos inválidos...). Nenhum dado real.
"""
from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

import openpyxl
from openpyxl.styles import Font

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "tests" / "dados_ficticios"
ACOUGUE, HORTI, FRIOS = 110, 120, 130

LOJAS = [  # nro, nome, regional, nome_regional
    (1, "CENTRO", 10, "REGIONAL NORTE"), (2, "JARDIM AMERICA", 10, "REGIONAL NORTE"),
    (3, "BELA VISTA", 10, "REGIONAL NORTE"), (5, "SANTA CRUZ", 20, "REGIONAL SUL"),
    (6, "VILA NOVA", 20, "REGIONAL SUL"), (7, "PORTO", 20, "REGIONAL SUL"),
    (8, "AEROPORTO", 30, "REGIONAL OESTE"), (9, "SHOPPING", None, None),
]
CORTES = ["ALCATRA", "PICANHA", "PATINHO", "COXAO MOLE", "FRALDINHA", "COSTELA", "CUPIM", "MAMINHA",
          "FRANGO INTEIRO", "COXA SOBRECOXA", "PEITO FRANGO", "LINGUICA TOSCANA", "PERNIL SUINO",
          "BISTECA SUINA", "CARNE MOIDA", "ACEM", "MUSCULO", "LAGARTO", "CONTRA FILE", "FILE MIGNON"]
FLV = ["BANANA PRATA", "MACA GALA", "LARANJA PERA", "MAMAO PAPAYA", "TOMATE", "BATATA", "CEBOLA",
       "ALFACE CRESPA", "CENOURA", "ABOBRINHA", "PEPINO", "UVA ITALIA", "MELANCIA", "MANGA TOMMY",
       "LIMAO TAHITI", "PIMENTAO VERDE", "BROCOLIS", "COUVE", "ABACAXI", "MORANGO"]


def produtos():
    ps = [(1000 + i, f"{n} KG", 500 + i, ACOUGUE, "ACOUGUE") for i, n in enumerate(CORTES)]
    ps += [(2000 + i, f"{n} KG", 700 + i, HORTI, "HORTIFRUTI") for i, n in enumerate(FLV)]
    frios = [(5001, "PRESUNTO FATIADO KG", 900, FRIOS, "FRIOS"), (5002, "QUEIJO MUSSARELA KG", 901, FRIOS, "FRIOS")]
    return ps, frios


def ean(seq: int) -> str:
    return f"789{seq:09d}"[:12] + "0"


def escrever(nome: str, cab: list[str], linhas: list[tuple]):
    with open(PASTA / f"{nome}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cab)
        w.writerows(linhas)


def gerar_consinco(rnd: random.Random):
    ps, frios = produtos()
    escrever("lojas", ["nro_empresa", "nome_loja", "nro_regional", "nome_regional", "nro_divisao", "cidade", "uf", "status"],
             [(n, nm, r or "", rn or "", 1, "CIDADE", "SP", "A") for n, nm, r, rn in LOJAS])
    escrever("produtos", ["seq_produto", "desc_produto", "seq_familia", "seq_categoria", "nome_categoria"], ps)
    escrever("produtos_todos", ["seq_produto", "desc_produto", "seq_familia", "seq_categoria", "nome_categoria"], ps + frios)
    escrever("produto_codigo", ["cod_acesso", "seq_produto", "tip_codigo"], [(ean(p[0]), p[0], "E") for p in ps])

    avarias, vendas = [], []
    d = date(2026, 9, 1)
    while d <= date(2026, 11, 15):
        for n, *_ in LOJAS:
            peso = 1 + (n % 4) * 0.35                    # algumas lojas perdem mais
            for cat, base in ((ACOUGUE, 9000), (HORTI, 6500)):
                bruta = round(base * (0.8 + rnd.random() * 0.5) * (1.2 if d.weekday() >= 4 else 1), 2)
                dev = round(bruta * rnd.random() * 0.01, 2)
                vendas.append((n, cat, d.isoformat(), bruta, dev, round(bruta - dev, 2)))
            for p in rnd.sample(ps, 4):
                for cgo in (403, 552):
                    if rnd.random() < 0.5:
                        q = round(rnd.random() * 5, 3)
                        v = round(q * (38 if p[3] == ACOUGUE else 7) * peso, 2)
                        avarias.append((n, p[0], d.isoformat(), cgo, p[3], q, v))
        d += timedelta(days=1)
    escrever("avarias", ["nro_empresa", "seq_produto", "dta_lancamento", "cgo", "seq_categoria", "qtd_lancada", "vlr_movimentacao"], avarias)
    escrever("vendas", ["nro_empresa", "seq_categoria", "dta_venda", "vlr_venda_bruta", "vlr_devolucao", "vlr_venda_liquida"], vendas)


def linhas_inventario(rnd: random.Random, cat: int, ate_outubro: bool, so_outubro: bool = False):
    ps, _ = produtos()
    ps = [p for p in ps if p[3] == cat]
    datas = [date(2026, 8, 20), date(2026, 9, 12), date(2026, 9, 26)]
    if ate_outubro:
        datas += [date(2026, 10, 10), date(2026, 10, 24)]
    if so_outubro:
        datas = [date(2026, 10, 10), date(2026, 10, 24)]
    blocos = []
    for n, nome, *_ in LOJAS[:7]:
        for dt in datas:
            itens = []
            for p in rnd.sample(ps, 6):
                v = round(rnd.uniform(-420, 120) * (1 + (n % 3) * 0.6), 2)   # maioria faltas, algumas sobras
                itens.append([p[0], p[1], dt, v])
            blocos.append((n, nome, dt, itens))
    return blocos


# (bloco, item) -> problema pontual; blocos com bi % 3 != 0 caem dentro do período
ESPECIAIS = {(1, 0): "inexistente", (2, 1): "frios", (4, 2): "texto", (5, 3): "data_impossivel",
             (7, 4): "data_futura", (8, 0): "loja_99", (13, 5): "sem_codigo", (14, 1): "loja_branco"}


def gerar_planilha(rnd: random.Random, ate_outubro: bool, so_outubro: bool = False):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    resumo = wb.create_sheet("Resumo")
    resumo["A1"] = "Resumo gerencial (aba fora do escopo do ETL)"
    for nome_aba, cat in (("AÇOUGUE", ACOUGUE), (" HORTIFRÚTI ", HORTI)):
        ws = wb.create_sheet(nome_aba)
        ws["A1"] = "GRUPO QUEIROZ — INVENTÁRIO GERAL E ROTATIVO 2025"
        ws["A1"].font = Font(bold=True, size=14)
        ws.merge_cells("A1:I1")
        ws["A2"] = f"Setor: {nome_aba.strip()}"
        cab = ["Loja", "Data Inventário", "Tipo", "Cód. Produto", "Descrição", "Qtd Sistema",
               "Qtd Contada", "Qtd Divergente", "Valor Divergente (R$)"]
        ws.append([])
        ws.append(cab)
        r = 5
        for bi, (n, nome, dt, itens) in enumerate(linhas_inventario(rnd, cat, ate_outubro, so_outubro)):
            ini = r
            for ii, (seq, desc, d, v) in enumerate(itens):
                loja_txt = [f"Loja {n:02d}", f"{n:02d} - {nome}", n, nome][bi % 4]
                data_cel: object = d
                valor: object = v
                codigo: object = seq
                k = (bi * 7 + ii) % 23
                # ---- problemas injetados -------------------------------------------------
                if k == 1: valor = f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                if k == 2 and v < 0: valor = f"({abs(v):,.2f})".replace(",", "X").replace(".", ",").replace("X", ".")
                if k == 3: valor = "#N/D"
                if k == 4: valor = None
                if k == 5: data_cel = d.strftime("%d/%m/%Y")
                if k == 6: data_cel = (d - date(1899, 12, 30)).days            # serial do Excel
                if k == 7: codigo = f"00{seq}"
                if k == 8: codigo = float(seq)
                if k == 9: codigo = ean(seq)                                    # EAN na coluna de código
                if k == 17: valor = 0
                esp = ESPECIAIS.get((bi, ii))
                if esp == "inexistente": codigo = 99999                         # não existe
                if esp == "frios": codigo = 5001                                # existe, mas é Frios
                if esp == "texto": codigo = "ABC-12"                            # não numérico
                if esp == "data_impossivel": data_cel = "31/02/2026"
                if esp == "data_futura": data_cel = date(2027, 1, 15)
                if esp == "loja_99": loja_txt = "Loja 99"                       # loja inexistente
                if esp == "sem_codigo": codigo = None
                if esp == "loja_branco": loja_txt = None                        # loja em branco (sem mescla)
                ws.append([loja_txt, data_cel, "ROTATIVO" if bi % 3 else "GERAL", codigo, desc,
                           10, 10, None, valor])
                r += 1
            # loja mesclada na vertical (só a 1ª célula tem valor) em alguns blocos
            if bi % 5 == 0 and r - ini > 1:
                for rr in range(ini + 1, r):
                    ws.cell(rr, 1).value = None
                ws.merge_cells(start_row=ini, start_column=1, end_row=r - 1, end_column=1)
            # duplicidades
            if bi == 16:
                ws.append([c.value for c in ws[r - 1]]); r += 1                 # linha idêntica
            if bi == 11:
                lin = [c.value for c in ws[r - 1]]
                lin[8] = -999.99
                ws.append(lin); r += 1                                          # mesma chave, outro valor
            if bi == 17:
                ws.append([None] * 9); r += 1
                ws.append(cab); r += 1                                          # cabeçalho repetido
            if bi == 19:
                ws.append([f"Loja {n:02d}", dt, "ROTATIVO", itens[0][0], itens[0][1], 1, 1, None, -12.5])
                ws.row_dimensions[r].hidden = True; r += 1                      # linha oculta
            ws.append(["TOTAL " + nome, None, None, None, None, None, None, None, f"=SUM(I{ini}:I{r - 1})"])
            r += 1
            ws.append([]); r += 1
        if cat == HORTI and ate_outubro:
            # bloco no formato "contexto": loja e data num título, sem preencher nas linhas
            ws.append(["LOJA 08 - AEROPORTO — Inventário rotativo 31/10/2026"]); r += 1
            for i in range(3):
                ws.append([None, None, "ROTATIVO", 2000 + i, FLV[i], 5, 4, -1, -15.3 * (i + 1)]); r += 1
    destino = RAIZ / "entrada" / "Inventário Geral e Rotativo 2025.xlsm"
    for antigo in (RAIZ / "entrada").glob("*.xls*"):
        antigo.unlink()
    wb.save(destino)
    return destino


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--outubro", action="store_true", help="gera a versão da planilha até outubro")
    ap.add_argument("--so-outubro", action="store_true", help="versão que traz SÓ outubro (teste de proteção)")
    a = ap.parse_args()
    PASTA.mkdir(parents=True, exist_ok=True)
    if not (a.outubro or a.so_outubro):
        gerar_consinco(random.Random(42))
    print("Planilha:", gerar_planilha(random.Random(7), a.outubro or a.so_outubro, a.so_outubro))
    print("CSVs em:", PASTA)
