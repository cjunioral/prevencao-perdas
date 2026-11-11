"""Carga das fontes da Consinco: cadastros (lojas, produtos) e movimentos
(avarias e vendas) por janela móvel. Cada fonte grava numa única transação."""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any

import psycopg

from .contexto import Contexto
from .controle import Rejeitado, ResultadoCarga, gravar_rejeitados
from .janela import Janela, blocos

log = logging.getLogger("carga.consinco")


def _copy(cur: psycopg.Cursor, tabela: str, colunas: list[str], linhas: list[dict[str, Any]]) -> None:
    with cur.copy(f"COPY {tabela} ({', '.join(colunas)}) FROM STDIN") as cp:
        for l in linhas:
            cp.write_row(tuple(l.get(c) for c in colunas))


# ----------------------------------------------------------------------------- lojas
def carregar_lojas(ctx: Contexto, id_carga: int) -> ResultadoCarga:
    linhas = ctx.consinco.consultar("lojas")
    if not linhas:
        raise RuntimeError("A extração de lojas veio vazia: confira 01_lojas.sql e o acesso à Consinco")
    r = ResultadoCarga(lidas=len(linhas))
    vistos: dict[int, dict] = {}
    for l in linhas:
        if l["nro_empresa"] in vistos:
            r.avisos["loja_duplicada_na_extracao"] = r.avisos.get("loja_duplicada_na_extracao", 0) + 1
            continue
        l["id_carga"] = id_carga
        vistos[l["nro_empresa"]] = l
    sem_regional = sum(1 for l in vistos.values() if l.get("nro_regional") is None)
    if sem_regional:
        r.avisos["loja_sem_regional"] = sem_regional

    with psycopg.connect(ctx.cfg.dsn_pg()) as con, con.cursor() as cur:
        cur.execute("DELETE FROM staging.consinco_loja")
        _copy(cur, "staging.consinco_loja",
              ["nro_empresa", "nome_loja", "nro_regional", "nome_regional", "nro_divisao",
               "cidade", "uf", "status", "id_carga"], list(vistos.values()))
        cur.execute("""
            INSERT INTO analitico.dim_regional (nro_regional, nome_regional)
            SELECT DISTINCT ON (nro_regional) nro_regional,
                   COALESCE(NULLIF(TRIM(nome_regional), ''), 'REGIONAL ' || nro_regional)
            FROM staging.consinco_loja WHERE nro_regional IS NOT NULL
            ORDER BY nro_regional
            ON CONFLICT (nro_regional) DO UPDATE
               SET nome_regional = EXCLUDED.nome_regional, dt_atualizacao = now()
             WHERE dim_regional.nome_regional IS DISTINCT FROM EXCLUDED.nome_regional""")
        cur.execute("""
            WITH up AS (
              INSERT INTO analitico.dim_loja (nro_empresa, nome_loja, nro_regional, cidade, uf, ativa)
              SELECT nro_empresa, TRIM(nome_loja), COALESCE(nro_regional, -1), TRIM(cidade),
                     LEFT(TRIM(uf), 2), COALESCE(status, 'A') = 'A'
              FROM staging.consinco_loja
              ON CONFLICT (nro_empresa) DO UPDATE
                 SET nome_loja = EXCLUDED.nome_loja, nro_regional = EXCLUDED.nro_regional,
                     cidade = EXCLUDED.cidade, uf = EXCLUDED.uf, ativa = EXCLUDED.ativa,
                     dt_atualizacao = now()
               WHERE (dim_loja.nome_loja, dim_loja.nro_regional, dim_loja.cidade, dim_loja.uf, dim_loja.ativa)
                     IS DISTINCT FROM
                     (EXCLUDED.nome_loja, EXCLUDED.nro_regional, EXCLUDED.cidade, EXCLUDED.uf, EXCLUDED.ativa)
              RETURNING (xmax = 0) AS inserido)
            SELECT COUNT(*) FILTER (WHERE inserido), COUNT(*) FILTER (WHERE NOT inserido) FROM up""")
        r.inseridas, r.atualizadas = cur.fetchone()
        # regional que ficou sem nenhuma loja (a regra mudou) sai da dimensão:
        # senão aparece vazia nos filtros do painel. O membro -1 fica sempre.
        cur.execute("""DELETE FROM analitico.dim_regional r
                        WHERE r.nro_regional <> -1
                          AND NOT EXISTS (SELECT 1 FROM analitico.dim_loja l
                                           WHERE l.nro_regional = r.nro_regional)""")
        if cur.rowcount:
            r.avisos["regionais_sem_loja_removidas"] = cur.rowcount
    r.carregadas = len(vistos)
    return r


# ----------------------------------------------------------------------------- produtos
def carregar_produtos(ctx: Contexto, id_carga: int) -> ResultadoCarga:
    cats = ctx.cfg.categorias
    params = {"nivel_categoria": ctx.cfg.nivel_categoria}
    produtos = ctx.consinco.consultar("produtos", params, {"categorias": cats.keys()})
    if not produtos:
        # proteção: categoria/nível errados no .env fariam a carga "passar" com zero produtos
        raise RuntimeError(f"Nenhum produto nas categorias {dict(cats)} no nível {ctx.cfg.nivel_categoria}: "
                           "confira CATEGORIAS_ESCOPO e NIVEL_CATEGORIA no .env")
    codigos = ctx.consinco.consultar("produto_codigo", params, {"categorias": cats.keys()})
    r = ResultadoCarga(lidas=len(produtos))

    unicos: dict[int, dict] = {}
    for p in produtos:
        if p["seq_produto"] in unicos:
            # família ligada a mais de uma categoria ativa: fica a primeira, e avisa
            r.avisos["produto_em_mais_de_uma_categoria"] = r.avisos.get("produto_em_mais_de_uma_categoria", 0) + 1
            continue
        p["id_carga"] = id_carga
        unicos[p["seq_produto"]] = p

    cods: dict[tuple[str, int], dict] = {}
    for c in codigos:
        cod = str(c["cod_acesso"]).strip().lstrip("0")
        if cod and c["seq_produto"] in unicos:
            cods[(cod, c["seq_produto"])] = {"cod_acesso": cod, "seq_produto": c["seq_produto"],
                                             "tip_codigo": c.get("tip_codigo"), "id_carga": id_carga}

    with psycopg.connect(ctx.cfg.dsn_pg()) as con, con.cursor() as cur:
        cur.execute("DELETE FROM staging.consinco_produto")
        cur.execute("DELETE FROM staging.consinco_produto_codigo")
        _copy(cur, "staging.consinco_produto",
              ["seq_produto", "desc_produto", "seq_familia", "seq_categoria", "nome_categoria", "id_carga"],
              list(unicos.values()))
        _copy(cur, "staging.consinco_produto_codigo",
              ["cod_acesso", "seq_produto", "tip_codigo", "id_carga"], list(cods.values()))
        # categorias do escopo, com o rótulo padronizado do .env
        for seq, rotulo in cats.items():
            cur.execute("""
                INSERT INTO analitico.dim_categoria (seq_categoria, nome_categoria, categoria)
                VALUES (%s, COALESCE((SELECT MAX(TRIM(nome_categoria)) FROM staging.consinco_produto
                                      WHERE seq_categoria = %s), %s), %s)
                ON CONFLICT (seq_categoria) DO UPDATE
                   SET nome_categoria = EXCLUDED.nome_categoria, categoria = EXCLUDED.categoria,
                       dt_atualizacao = now()""", (seq, seq, rotulo, rotulo))
        cur.execute("""
            WITH up AS (
              INSERT INTO analitico.dim_produto (seq_produto, desc_produto, seq_familia, seq_categoria)
              SELECT seq_produto, TRIM(desc_produto), seq_familia, seq_categoria FROM staging.consinco_produto
              ON CONFLICT (seq_produto) DO UPDATE
                 SET desc_produto = EXCLUDED.desc_produto, seq_familia = EXCLUDED.seq_familia,
                     seq_categoria = EXCLUDED.seq_categoria, dt_atualizacao = now()
               WHERE (dim_produto.desc_produto, dim_produto.seq_familia, dim_produto.seq_categoria)
                     IS DISTINCT FROM (EXCLUDED.desc_produto, EXCLUDED.seq_familia, EXCLUDED.seq_categoria)
              RETURNING (xmax = 0) AS inserido)
            SELECT COUNT(*) FILTER (WHERE inserido), COUNT(*) FILTER (WHERE NOT inserido) FROM up""")
        r.inseridas, r.atualizadas = cur.fetchone()
        cur.execute("DELETE FROM analitico.produto_codigo")
        cur.execute("""INSERT INTO analitico.produto_codigo (cod_acesso, seq_produto)
                       SELECT cod_acesso, seq_produto FROM staging.consinco_produto_codigo""")
    r.carregadas = len(unicos)
    r.avisos["codigos_ean"] = len(cods)
    return r


# ----------------------------------------------------------------------------- movimentos
MOVIMENTOS = {
    "avaria": {
        "consulta": "avarias", "fonte": "consinco_avaria",
        "staging": "staging.consinco_avaria", "col_data": "dta_lancamento",
        "staging_cols": ["nro_empresa", "seq_produto", "dta_lancamento", "cgo", "seq_categoria",
                         "qtd_lancada", "vlr_movimentacao", "id_carga"],
        "valor": "vlr_movimentacao",
        "fato": "analitico.fato_avaria",
        "tmp": """CREATE TEMP TABLE tmp_mov (nro_empresa int, seq_produto bigint, data date, cgo int,
                    seq_categoria int, qtd_lancada numeric(18,3), vlr_avaria numeric(18,2)) ON COMMIT DROP""",
        "tmp_cols": ["nro_empresa", "seq_produto", "data", "cgo", "seq_categoria", "qtd_lancada", "vlr_avaria"],
        "upsert": """
            WITH up AS (
              INSERT INTO analitico.fato_avaria (nro_empresa, seq_produto, data, cgo, seq_categoria,
                                                 qtd_lancada, vlr_avaria, id_carga)
              SELECT nro_empresa, seq_produto, data, cgo, MAX(seq_categoria),
                     SUM(qtd_lancada), SUM(vlr_avaria), %(id_carga)s
              FROM tmp_mov GROUP BY nro_empresa, seq_produto, data, cgo
              ON CONFLICT (nro_empresa, seq_produto, data, cgo) DO UPDATE
                 SET seq_categoria = EXCLUDED.seq_categoria, qtd_lancada = EXCLUDED.qtd_lancada,
                     vlr_avaria = EXCLUDED.vlr_avaria, id_carga = EXCLUDED.id_carga, dt_atualizacao = now()
               WHERE (fato_avaria.seq_categoria, fato_avaria.qtd_lancada, fato_avaria.vlr_avaria)
                     IS DISTINCT FROM (EXCLUDED.seq_categoria, EXCLUDED.qtd_lancada, EXCLUDED.vlr_avaria)
              RETURNING (xmax = 0) AS inserido)
            SELECT COUNT(*) FILTER (WHERE inserido), COUNT(*) FILTER (WHERE NOT inserido) FROM up""",
        "delete": """
            DELETE FROM analitico.fato_avaria f
            WHERE f.data BETWEEN %(ini)s AND %(fim)s
              AND NOT EXISTS (SELECT 1 FROM tmp_mov t
                              WHERE t.nro_empresa = f.nro_empresa AND t.seq_produto = f.seq_produto
                                AND t.data = f.data AND t.cgo = f.cgo)""",
    },
    "venda": {
        "consulta": "vendas", "fonte": "consinco_venda",
        "staging": "staging.consinco_venda", "col_data": "dta_venda",
        "staging_cols": ["nro_empresa", "seq_categoria", "dta_venda", "vlr_venda_bruta",
                         "vlr_devolucao", "vlr_venda_liquida", "id_carga"],
        "valor": "vlr_venda_liquida",
        "fato": "analitico.fato_venda",
        "tmp": """CREATE TEMP TABLE tmp_mov (nro_empresa int, seq_categoria int, data date,
                    vlr_venda_bruta numeric(18,2), vlr_devolucao numeric(18,2),
                    vlr_venda_liquida numeric(18,2)) ON COMMIT DROP""",
        "tmp_cols": ["nro_empresa", "seq_categoria", "data", "vlr_venda_bruta", "vlr_devolucao", "vlr_venda_liquida"],
        "upsert": """
            WITH up AS (
              INSERT INTO analitico.fato_venda (nro_empresa, seq_categoria, data, vlr_venda_bruta,
                                                vlr_devolucao, vlr_venda_liquida, id_carga)
              SELECT nro_empresa, seq_categoria, data, SUM(vlr_venda_bruta), SUM(vlr_devolucao),
                     SUM(vlr_venda_liquida), %(id_carga)s
              FROM tmp_mov GROUP BY nro_empresa, seq_categoria, data
              ON CONFLICT (nro_empresa, seq_categoria, data) DO UPDATE
                 SET vlr_venda_bruta = EXCLUDED.vlr_venda_bruta, vlr_devolucao = EXCLUDED.vlr_devolucao,
                     vlr_venda_liquida = EXCLUDED.vlr_venda_liquida, id_carga = EXCLUDED.id_carga,
                     dt_atualizacao = now()
               WHERE (fato_venda.vlr_venda_bruta, fato_venda.vlr_devolucao, fato_venda.vlr_venda_liquida)
                     IS DISTINCT FROM (EXCLUDED.vlr_venda_bruta, EXCLUDED.vlr_devolucao, EXCLUDED.vlr_venda_liquida)
              RETURNING (xmax = 0) AS inserido)
            SELECT COUNT(*) FILTER (WHERE inserido), COUNT(*) FILTER (WHERE NOT inserido) FROM up""",
        "delete": """
            DELETE FROM analitico.fato_venda f
            WHERE f.data BETWEEN %(ini)s AND %(fim)s
              AND NOT EXISTS (SELECT 1 FROM tmp_mov t
                              WHERE t.nro_empresa = f.nro_empresa AND t.seq_categoria = f.seq_categoria
                                AND t.data = f.data)""",
    },
}


def carregar_movimento(ctx: Contexto, tipo: str, janela: Janela, id_carga: int) -> ResultadoCarga:
    m = MOVIMENTOS[tipo]
    cfg = ctx.cfg
    listas: dict[str, Any] = {"categorias": cfg.categorias.keys()}
    if tipo == "avaria":
        listas["cgos"] = cfg.cgos_avaria

    linhas: list[dict[str, Any]] = []
    for ini, fim_excl in blocos(janela, cfg.bloco_dias):
        bloco = ctx.consinco.consultar(m["consulta"], {"dt_ini": ini, "dt_fim": fim_excl,
                                                       "nivel_categoria": cfg.nivel_categoria}, listas)
        log.info("  %s %s a %s: %d linhas", tipo, ini, fim_excl, len(bloco))
        linhas.extend(bloco)

    r = ResultadoCarga(lidas=len(linhas))
    with psycopg.connect(cfg.dsn_pg()) as con, con.cursor() as cur:
        lojas = {x[0] for x in cur.execute("SELECT nro_empresa FROM analitico.dim_loja")}
        produtos = {x[0] for x in cur.execute("SELECT seq_produto FROM analitico.dim_produto")}

        validas, rejeitados, avisos = [], [], Counter()
        for i, l in enumerate(linhas, start=1):
            data = l[m["col_data"]]
            data = data.date() if hasattr(data, "date") else data
            l[m["col_data"]] = data
            l["id_carga"] = id_carga
            if l["nro_empresa"] not in lojas:
                rejeitados.append(Rejeitado(i, l, "LOJA_NAO_CADASTRADA", f"loja {l['nro_empresa']}"))
            elif tipo == "avaria" and l["seq_produto"] not in produtos:
                rejeitados.append(Rejeitado(i, l, "PRODUTO_NAO_ENCONTRADO",
                                            f"produto {l['seq_produto']} fora da dimensão"))
            elif l[m["valor"]] is None:
                rejeitados.append(Rejeitado(i, l, "VALOR_NULO_CONSINCO", m["valor"]))
            else:
                if l[m["valor"]] < 0:
                    avisos[f"{m['valor']}_negativo"] += 1   # estorno/devolução > venda: mantido e sinalizado
                t = dict(l, data=data)
                if tipo == "avaria":
                    t["vlr_avaria"] = l["vlr_movimentacao"]
                validas.append(t)

        # staging: substitui a mesma janela (fica como veio, inclusive o que foi rejeitado)
        cur.execute(f"DELETE FROM {m['staging']} WHERE {m['col_data']} BETWEEN %s AND %s",
                    (janela.inicio, janela.fim))
        _copy(cur, m["staging"], m["staging_cols"], linhas)

        # analítico: sincroniza a janela (upsert + remoção do que sumiu da fonte)
        cur.execute(m["tmp"])
        _copy(cur, "tmp_mov", m["tmp_cols"], validas)
        cur.execute(m["upsert"], {"id_carga": id_carga})
        r.inseridas, r.atualizadas = cur.fetchone()
        cur.execute(m["delete"], {"ini": janela.inicio, "fim": janela.fim})
        r.removidas = cur.rowcount
        gravar_rejeitados(cur, id_carga, m["fonte"], rejeitados)

    r.carregadas, r.rejeitadas, r.avisos = len(validas), len(rejeitados), dict(avisos)
    return r
