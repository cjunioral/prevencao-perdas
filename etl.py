"""Processo de carga — Prevenção de Perdas (Açougue e Hortifruti).

Uso:
    python etl.py                         # carga diária (o que o agendador roda às 06h00)
    python etl.py --modo completo         # recarrega o período inteiro (fora do horário comercial)
    python etl.py --modo completo --inicio 2026-09-01 --fim 2026-09-30
    python etl.py --fontes planilha       # só a planilha
    python etl.py --forcar-planilha       # reprocessa a planilha mesmo sem alteração
    python etl.py --data-referencia 2026-11-10   # simula a execução de outro dia (testes)

Ordem: cadastros da Consinco -> avarias -> vendas -> planilha. Cada fonte é
independente: se uma falha, o erro é registrado e as outras seguem.

Códigos de saída: 0 sucesso | 1 sucesso parcial | 2 falha | 3 bloqueada (outra execução em andamento)
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
import traceback
from datetime import date

from etl import carga_consinco, carga_planilha, janela
from etl import log as etl_log
from etl.config import Config
from etl.contexto import Contexto
from etl.controle import Controle, ResultadoCarga
from etl.trava import Trava

log = logging.getLogger("etl")


def argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modo", choices=["diario", "completo"], default="diario")
    p.add_argument("--inicio", type=date.fromisoformat)
    p.add_argument("--fim", type=date.fromisoformat)
    p.add_argument("--data-referencia", type=date.fromisoformat, default=date.today())
    p.add_argument("--fontes", default="consinco,planilha", help="consinco,planilha")
    p.add_argument("--forcar-planilha", action="store_true")
    p.add_argument("--ignorar-horario", action="store_true",
                   help="permite carga grande em horário comercial (use com consciência)")
    return p.parse_args()


def executar_fonte(ctx: Contexto, fonte: str, funcao, **kw_carga) -> str:
    """Envolve uma carga com registro em controle.carga e falha controlada."""
    id_c = ctx.controle.iniciar_carga(ctx.id_execucao, fonte, **kw_carga)
    t0 = time.monotonic()
    try:
        r: ResultadoCarga = funcao(id_c)
        ctx.controle.finalizar_carga(id_c, "SUCESSO", r)
        log.info("%-18s OK em %.1fs | %s%s", fonte, time.monotonic() - t0, r.resumo(),
                 f" | avisos {r.avisos}" if r.avisos else "")
        return "SUCESSO"
    except PermissionError as e:                       # regra de horário comercial
        ctx.controle.finalizar_carga(id_c, "IGNORADA", mensagem=str(e))
        log.warning("%-18s IGNORADA: %s", fonte, e)
        return "IGNORADA"
    except Exception as e:  # noqa: BLE001 — falha controlada
        ctx.controle.finalizar_carga(id_c, "FALHA", mensagem=f"{type(e).__name__}: {e}")
        log.error("%-18s FALHOU: %s\n%s", fonte, e, traceback.format_exc())
        return "FALHA"


def _levantar(e: Exception):
    raise e


def rodar_consinco(ctx: Contexto, args: argparse.Namespace) -> list[str]:
    st = [executar_fonte(ctx, "consinco_lojas", lambda id_c: carga_consinco.carregar_lojas(ctx, id_c)),
          executar_fonte(ctx, "consinco_produtos", lambda id_c: carga_consinco.carregar_produtos(ctx, id_c))]
    for tipo, fonte in (("avaria", "consinco_avaria"), ("venda", "consinco_venda")):
        try:
            j = janela.calcular(ctx.cfg, args.modo, ctx.data_ref, ctx.controle.ultimo_fim_sucesso(fonte),
                                args.inicio, args.fim, args.ignorar_horario)
        except PermissionError as e:
            st.append(executar_fonte(ctx, fonte, lambda _id, e=e: _levantar(e)))
            continue
        if j is None:
            log.info("%-18s nada a carregar (período encerrado ou já carregado)", fonte)
            continue
        log.info("%-18s janela %s a %s (%d dias) — %s", fonte, j.inicio, j.fim, j.dias, j.observacao)
        st.append(executar_fonte(ctx, fonte, lambda id_c, t=tipo, j=j: carga_consinco.carregar_movimento(ctx, t, j, id_c),
                                 periodo_inicio=j.inicio, periodo_fim=j.fim))
    return st


def main() -> int:
    args = argumentos()
    cfg = Config()
    arquivo_log = etl_log.configurar(cfg.pasta_logs)
    fontes = {f.strip() for f in args.fontes.split(",")}
    log.info("=" * 78)
    log.info("INÍCIO | modo=%s data_ref=%s fontes=%s consinco=%s | log em %s",
             args.modo, args.data_referencia, sorted(fontes), cfg.consinco_modo, arquivo_log)

    try:
        controle = Controle(cfg.dsn_pg())
    except Exception as e:  # noqa: BLE001 — sem banco não há onde gravar nada
        log.critical("Banco analítico indisponível: %s", e)
        return 2

    parametros = {k: str(v) for k, v in vars(args).items()}
    with Trava(cfg.dsn_pg()) as trava:
        if not trava.obtida:
            id_e = controle.iniciar_execucao(args.modo, args.data_referencia, parametros)
            controle.finalizar_execucao(id_e, "BLOQUEADA", "outra execução em andamento")
            log.warning("FIM | outra execução está em andamento; esta foi encerrada sem alterar dados")
            controle.close()
            return 3

        id_e = controle.iniciar_execucao(args.modo, args.data_referencia, parametros)
        ctx = Contexto(cfg, controle, id_e, args.data_referencia)
        status: list[str] = []
        try:
            if "consinco" in fontes:
                status += rodar_consinco(ctx, args)
            if "planilha" in fontes:
                status += carga_planilha.processar(ctx, args.forcar_planilha)
        finally:
            ctx.fechar()

        falhas = status.count("FALHA")
        final = "FALHA" if status and falhas == len(status) else "SUCESSO_PARCIAL" if falhas else "SUCESSO"
        controle.finalizar_execucao(id_e, final, f"{len(status)} cargas: " +
                                    ", ".join(f"{s}={status.count(s)}" for s in sorted(set(status))))
        log.info("FIM | execução %d: %s (%s)", id_e, final, ", ".join(status))
        controle.close()
    return {"SUCESSO": 0, "SUCESSO_PARCIAL": 1, "FALHA": 2}[final]


if __name__ == "__main__":
    sys.exit(main())
