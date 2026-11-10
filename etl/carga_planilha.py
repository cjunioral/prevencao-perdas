"""Carga da planilha de inventário (perda não identificada).

Versionamento: o processo calcula o SHA-256 do arquivo. Se o conteúdo é o
mesmo da última carga bem-sucedida daquela aba, não reprocessa (IGNORADA). Se
mudou, a nova versão SUBSTITUI os dados da anterior daquela aba, numa única
transação (apaga as linhas com aba_origem = aba e insere as novas). O nome do
arquivo não importa: vale o conteúdo.

Cada aba é uma carga independente: se Hortifruti vier quebrada, Açougue é
carregado normalmente e Hortifruti mantém os dados da versão anterior.
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import tempfile
import time
import traceback
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import psycopg

from .contexto import Contexto
from .controle import Rejeitado, ResultadoCarga, gravar_rejeitados
from .fontes import planilha as pl
from .qualidade import parse_codigo, parse_data, parse_loja, parse_valor, texto_normalizado, vazio

log = logging.getLogger("carga.planilha")
FONTE = "planilha_inventario"
DATA_MINIMA = date(2020, 1, 1)


# ----------------------------------------------------------------------------- arquivo
def localizar(ctx: Contexto) -> Path | None:
    pasta = ctx.cfg.pasta_entrada
    candidatos = [p for p in pasta.glob(ctx.cfg.padrao_planilha)
                  if p.is_file() and not p.name.startswith(("~$", "."))]   # ~$ = arquivo de trava do Excel
    if not candidatos:
        return None
    candidatos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if len(candidatos) > 1:
        log.warning("Mais de uma planilha em %s; usando a mais recente: %s (ignoradas: %s)",
                    pasta, candidatos[0].name, [p.name for p in candidatos[1:]])
    return candidatos[0]


def copia_estavel(origem: Path) -> Path:
    """Copia para um temporário depois de confirmar que o arquivo não está sendo gravado
    (tamanho estável). Ler da cópia evita conflito com o Excel aberto."""
    t1 = origem.stat().st_size
    time.sleep(1)
    if origem.stat().st_size != t1:
        raise RuntimeError(f"{origem.name} ainda está sendo copiado/gravado; tente na próxima execução")
    destino = Path(tempfile.mkdtemp(prefix="etl_planilha_")) / origem.name
    shutil.copy2(origem, destino)
    return destino


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


# ----------------------------------------------------------------------------- cruzamento
class Cadastros:
    def __init__(self, con: psycopg.Connection):
        self.lojas = dict(con.execute("SELECT nro_empresa, nome_loja FROM analitico.dim_loja").fetchall())
        self.nomes_loja = {texto_normalizado(n): k for k, n in self.lojas.items()}
        self.produtos = dict(con.execute("SELECT seq_produto, seq_categoria FROM analitico.dim_produto").fetchall())
        self.ean: dict[str, set[int]] = defaultdict(set)
        for cod, seq in con.execute("SELECT cod_acesso, seq_produto FROM analitico.produto_codigo"):
            self.ean[cod].add(seq)
        self.categorias = dict(con.execute("SELECT seq_categoria, categoria FROM analitico.dim_categoria").fetchall())
        if not self.lojas or not self.produtos:
            raise RuntimeError("Cadastros vazios: rode a carga da Consinco antes da planilha")

    def produto(self, codigo: str | None, ean: str | None, avisos: Counter) -> int | None:
        for cod, eh_ean in ((codigo, False), (ean, True)):
            if not cod:
                continue
            if not eh_ean and len(cod) <= 7 and int(cod) in self.produtos:
                return int(cod)
            if cod in self.ean:
                if len(self.ean[cod]) > 1:
                    avisos["ean_com_mais_de_um_produto"] += 1
                if not eh_ean:
                    avisos["codigo_interpretado_como_ean"] += 1
                return min(self.ean[cod])
        return None


def cruzar(ctx: Contexto, aba: pl.AbaLida, cad: Cadastros, existentes_outra_aba: dict[tuple, str]
           ) -> tuple[list[dict], list[Rejeitado], Counter, set[date]]:
    cfg = ctx.cfg
    avisos: Counter = Counter(aba.avisos)
    fim_periodo = min(cfg.periodo_fim, ctx.data_ref) if cfg.periodo_fim else ctx.data_ref
    candidatas: list[tuple[pl.LinhaBruta, dict]] = []
    rejeitados: list[Rejeitado] = []
    pendentes_diag: dict[str, list[int]] = defaultdict(list)    # código -> índices em rejeitados
    meses: set[date] = set()                                    # meses presentes nesta versão do arquivo

    for lb in aba.linhas:
        if lb.classificacao:
            rejeitados.append(Rejeitado(lb.linha, lb.original, lb.classificacao))
            continue
        c = lb.campos
        problemas: list[tuple[str, str]] = []

        loja, p = parse_loja(c.get("loja"), cad.nomes_loja)
        if p:
            problemas.append((p, f"loja='{c.get('loja')}'"))
        elif loja not in cad.lojas:
            problemas.append(("LOJA_NAO_ENCONTRADA", f"loja={loja} não existe na Consinco"))

        cod, ean = parse_codigo(c.get("codigo")), parse_codigo(c.get("ean"))
        seq = cad.produto(cod, ean, avisos)
        if seq is None:
            if not cod and not ean:
                if vazio(c.get("codigo")) and vazio(c.get("ean")):
                    problemas.append(("PRODUTO_AUSENTE", "sem código"))
                else:
                    problemas.append(("PRODUTO_NAO_ENCONTRADO", f"código não numérico '{c.get('codigo') or c.get('ean')}'"))
            else:
                problemas.append(("PRODUTO_NAO_ENCONTRADO", f"código={cod or ean}"))
        elif cad.produtos.get(seq) is None:
            problemas.append(("PRODUTO_SEM_CATEGORIA", f"produto={seq}"))

        data, p = parse_data(c.get("data"), avisos, DATA_MINIMA, ctx.data_ref)
        if data:
            meses.add(data.replace(day=1))
        if p:
            problemas.append((p, f"data='{c.get('data')}'"))
        elif not (cfg.periodo_inicio <= data <= fim_periodo):
            problemas.append(("FORA_DO_PERIODO", f"data={data}"))

        valor, p = parse_valor(c.get("valor"), avisos)
        if p:
            det = f"valor='{c.get('valor')}'"
            if "_formula_valor" in lb.original:
                det += f" (fórmula sem valor calculado: {lb.original['_formula_valor']})"
            problemas.append((p, det))

        if problemas:
            # motivo principal = o primeiro; detalhe lista todos (ajuda a área a corrigir de uma vez)
            r = Rejeitado(lb.linha, lb.original, problemas[0][0], "; ".join(d for _, d in problemas))
            rejeitados.append(r)
            if problemas[0][0] == "PRODUTO_NAO_ENCONTRADO" and cod and len(cod) <= 7:
                pendentes_diag[cod].append(len(rejeitados) - 1)
            continue

        cat = cad.produtos[seq]
        if cad.categorias.get(cat) != aba.rotulo:
            avisos["categoria_consinco_difere_da_aba"] += 1     # vale a categoria da Consinco
        candidatas.append((lb, {"nro_empresa": loja, "seq_produto": seq, "data": data,
                                "seq_categoria": cat, "vlr_divergente": valor,
                                "linha_origem": lb.linha}))

    _diagnosticar(ctx, pendentes_diag, rejeitados)
    validas = _deduplicar(cfg.duplicidade, candidatas, rejeitados, avisos, existentes_outra_aba)
    return validas, rejeitados, avisos, meses


def _diagnosticar(ctx: Contexto, pendentes: dict[str, list[int]], rejeitados: list[Rejeitado]) -> None:
    """Para códigos sem par no escopo, pergunta à Consinco se o produto existe em
    outra categoria. Muda o motivo para PRODUTO_FORA_ESCOPO quando existe."""
    if not pendentes:
        return
    try:
        codigos = list(pendentes)
        existentes: dict[int, str] = {}
        for i in range(0, len(codigos), 500):
            for p in ctx.consinco.consultar("produto_por_codigo", listas={"codigos": [int(c) for c in codigos[i:i + 500]]}):
                existentes[int(p["seq_produto"])] = p.get("desc_produto") or ""
    except Exception as e:  # noqa: BLE001 — diagnóstico é opcional
        log.warning("Diagnóstico de produtos indisponível (%s); mantidos como PRODUTO_NAO_ENCONTRADO", e)
        return
    for cod, idxs in pendentes.items():
        if int(cod) in existentes:
            for i in idxs:
                rejeitados[i].motivo = "PRODUTO_FORA_ESCOPO"
                rejeitados[i].detalhe = f"produto {cod} ({existentes[int(cod)]}) não é Açougue/Hortifruti na Consinco"


def _deduplicar(estrategia: str, candidatas: list[tuple[pl.LinhaBruta, dict]], rejeitados: list[Rejeitado],
                avisos: Counter, existentes_outra_aba: dict[tuple, str]) -> list[dict]:
    grupos: dict[tuple, list[tuple[pl.LinhaBruta, dict]]] = defaultdict(list)
    for lb, v in candidatas:
        grupos[(v["nro_empresa"], v["seq_produto"], v["data"])].append((lb, v))

    validas = []
    for chave, itens in grupos.items():
        if chave in existentes_outra_aba:
            for lb, _ in itens:
                rejeitados.append(Rejeitado(lb.linha, lb.original, "DUPLICIDADE_CONFLITANTE",
                                            f"mesma loja/produto/data já carregada pela aba {existentes_outra_aba[chave]}"))
            continue
        if len(itens) == 1:
            validas.append(itens[0][1])
            continue
        valores = {v["vlr_divergente"] for _, v in itens}
        if len(valores) == 1:                                    # repetida idêntica: fica a primeira
            validas.append(itens[0][1])
            for lb, _ in itens[1:]:
                rejeitados.append(Rejeitado(lb.linha, lb.original, "LINHA_DUPLICADA",
                                            f"igual à linha {itens[0][0].linha}"))
        elif estrategia == "somar":                              # ex.: mesmo item contado em 2 locais
            v = dict(itens[0][1], vlr_divergente=sum(x["vlr_divergente"] for _, x in itens))
            validas.append(v)
            avisos["linhas_somadas_mesma_chave"] += len(itens) - 1
        else:                                                    # não dá para saber qual vale
            linhas = ", ".join(str(lb.linha) for lb, _ in itens)
            for lb, _ in itens:
                rejeitados.append(Rejeitado(lb.linha, lb.original, "DUPLICIDADE_CONFLITANTE",
                                            f"valores diferentes para a mesma chave nas linhas {linhas}"))
    return validas


# ----------------------------------------------------------------------------- gravação
def gravar(ctx: Contexto, aba: pl.AbaLida, arquivo: str, id_carga: int) -> ResultadoCarga:
    with psycopg.connect(ctx.cfg.dsn_pg()) as con:
        cad = Cadastros(con)
        outras = {(a, b, c): aba_o for a, b, c, aba_o in con.execute(
            """SELECT nro_empresa, seq_produto, data, aba_origem FROM analitico.fato_perda_inventario
               WHERE aba_origem <> %s""", (aba.rotulo,))}
        validas, rejeitados, avisos, meses = cruzar(ctx, aba, cad, outras)

        with con.cursor() as cur:
            # staging: a versão anterior desta aba sai, a nova entra como veio
            cur.execute("""DELETE FROM staging.planilha_inventario WHERE id_carga IN
                           (SELECT id_carga FROM controle.carga WHERE fonte = %s AND aba = %s)""",
                        (FONTE, aba.rotulo))
            with cur.copy("""COPY staging.planilha_inventario (id_carga, arquivo, aba, linha_origem, loja_texto,
                             produto_texto, descricao_texto, data_texto, valor_texto, registro_original)
                             FROM STDIN""") as cp:
                for lb in aba.linhas:
                    c = lb.campos
                    s = lambda k: None if c.get(k) is None else str(c.get(k))  # noqa: E731
                    cp.write_row((id_carga, arquivo, aba.nome_aba, lb.linha, s("loja"),
                                  s("codigo") or s("ean"), s("descricao"), s("data"), s("valor"),
                                  json.dumps(lb.original, default=str, ensure_ascii=False)))
            # analítico: a nova versão substitui, na aba, os MESES que ela contém.
            # Mês que existia e sumiu do arquivo é mantido (e avisado): protege
            # contra uma versão que traga só o mês novo e apagaria o histórico.
            cur.execute("""DELETE FROM analitico.fato_perda_inventario
                           WHERE aba_origem = %s AND date_trunc('month', data)::date = ANY(%s)""",
                        (aba.rotulo, sorted(meses)))
            removidas = cur.rowcount
            mantidos = [m for (m,) in cur.execute(
                """SELECT DISTINCT date_trunc('month', data)::date FROM analitico.fato_perda_inventario
                   WHERE aba_origem = %s ORDER BY 1""", (aba.rotulo,))]
            if mantidos:
                avisos["meses_mantidos_da_versao_anterior"] = len(mantidos)
                log.warning("Aba %s: meses %s não vieram na nova versão e foram MANTIDOS da anterior",
                            aba.rotulo, [m.strftime("%Y-%m") for m in mantidos])
            with cur.copy("""COPY analitico.fato_perda_inventario (nro_empresa, seq_produto, data, seq_categoria,
                             vlr_divergente, aba_origem, arquivo_origem, linha_origem, id_carga) FROM STDIN""") as cp:
                for v in validas:
                    cp.write_row((v["nro_empresa"], v["seq_produto"], v["data"], v["seq_categoria"],
                                  v["vlr_divergente"], aba.rotulo, arquivo, v["linha_origem"], id_carga))
            gravar_rejeitados(cur, id_carga, FONTE, rejeitados, arquivo, aba.nome_aba)

    somadas = avisos.get("linhas_somadas_mesma_chave", 0)
    r = ResultadoCarga(lidas=len(aba.linhas), carregadas=len(validas), rejeitadas=len(rejeitados),
                       inseridas=len(validas), removidas=removidas, avisos=dict(avisos))
    # conferência: nenhuma linha some sem registro
    assert r.lidas == r.carregadas + r.rejeitadas + somadas, \
        f"linhas não fecham: lidas={r.lidas} carregadas={r.carregadas} rejeitadas={r.rejeitadas} somadas={somadas}"
    return r


def processar(ctx: Contexto, forcar: bool = False) -> list[str]:
    """Devolve a lista de status das cargas desta fonte (para o status da execução)."""
    ctl, status = ctx.controle, []
    origem = localizar(ctx)
    if origem is None:
        id_c = ctl.iniciar_carga(ctx.id_execucao, FONTE)
        ctl.finalizar_carga(id_c, "IGNORADA", mensagem=f"nenhuma planilha em {ctx.cfg.pasta_entrada}")
        log.info("Nenhuma planilha na pasta de entrada; mantidos os dados atuais")
        return ["IGNORADA"]

    try:
        copia = copia_estavel(origem)
        hash_arq = sha256(copia)
    except Exception as e:  # noqa: BLE001
        id_c = ctl.iniciar_carga(ctx.id_execucao, FONTE, arquivo=origem.name)
        ctl.finalizar_carga(id_c, "FALHA", mensagem=str(e))
        log.error("Planilha %s: %s", origem.name, e)
        return ["FALHA"]
    log.info("Planilha %s (sha256 %s…)", origem.name, hash_arq[:12])

    pendentes = []
    for rotulo in pl.ABAS:
        if not forcar and ctl.ultimo_hash_sucesso(FONTE, rotulo) == hash_arq:
            id_c = ctl.iniciar_carga(ctx.id_execucao, FONTE, arquivo=origem.name, aba=rotulo, hash_arquivo=hash_arq)
            ctl.finalizar_carga(id_c, "IGNORADA", mensagem="arquivo sem alteração desde a última carga")
            log.info("Aba %s: arquivo sem alteração, nada a fazer", rotulo)
            status.append("IGNORADA")
        else:
            pendentes.append(rotulo)
    if not pendentes:
        return status

    try:
        wb_v, wb_f = pl.abrir(copia)
        abas, ocultas = pl.localizar_abas(wb_v)
        if ocultas:
            log.info("Abas parecidas IGNORADAS (ocultas/histórico): %d (%s...)", len(ocultas), ocultas[:3])
        outras = [n for n in wb_v.sheetnames if n not in abas.values() and n not in ocultas]
        if outras:
            log.info("Abas fora do escopo ignoradas: %s", outras)
        log.info("Abas usadas: %s", abas)
    except Exception as e:  # noqa: BLE001 — arquivo corrompido, senha, formato errado
        for rotulo in pendentes:
            id_c = ctl.iniciar_carga(ctx.id_execucao, FONTE, arquivo=origem.name, aba=rotulo, hash_arquivo=hash_arq)
            ctl.finalizar_carga(id_c, "FALHA", mensagem=f"não foi possível abrir a planilha: {e}")
        log.error("Não foi possível abrir %s: %s", origem.name, e)
        return status + ["FALHA"] * len(pendentes)

    for rotulo in pendentes:
        id_c = ctl.iniciar_carga(ctx.id_execucao, FONTE, arquivo=origem.name, aba=rotulo, hash_arquivo=hash_arq,
                                 periodo_inicio=ctx.cfg.periodo_inicio, periodo_fim=ctx.cfg.periodo_fim)
        try:
            if rotulo not in abas:
                raise pl.ErroEstrutura(f"aba de {rotulo} não encontrada (abas: {wb_v.sheetnames})")
            aba = pl.ler_aba(wb_v, wb_f, rotulo, abas[rotulo])
            r = gravar(ctx, aba, origem.name, id_c)
            ctl.finalizar_carga(id_c, "SUCESSO", r)
            log.info("Aba %s: %s", rotulo, r.resumo())
            if r.avisos:
                log.info("Aba %s: tratamentos aplicados %s", rotulo, r.avisos)
            status.append("SUCESSO")
        except Exception as e:  # noqa: BLE001 — falha controlada por aba
            ctl.finalizar_carga(id_c, "FALHA", mensagem=f"{type(e).__name__}: {e}")
            log.error("Aba %s FALHOU (dados anteriores mantidos): %s\n%s", rotulo, e, traceback.format_exc())
            status.append("FALHA")
    shutil.rmtree(copia.parent, ignore_errors=True)
    return status
