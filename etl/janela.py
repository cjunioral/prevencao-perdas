"""Cálculo da janela de reprocessamento da Consinco.

Problema: lançamentos e vendas podem ser incluídos ou corrigidos com data
retroativa, e a carga diária não pode apagar e recarregar o período inteiro.

Solução: janela móvel. Todo dia o processo reextrai só os últimos N dias
(JANELA_RETROATIVA_DIAS, padrão 40) e sincroniza essa janela no analítico:
  * linha nova na fonte        -> INSERT
  * linha alterada na fonte    -> UPDATE (só se algum valor mudou)
  * linha que sumiu da fonte   -> DELETE (estorno/exclusão dentro da janela)
Fora da janela nada é tocado. 40 dias cobre o mês corrente inteiro mais o
fechamento do mês anterior, que é quando a maioria das correções acontece.

Proteções adicionais:
  * primeira execução (nunca houve sucesso): carrega desde PERIODO_INICIO;
  * buraco (a máquina ficou desligada mais que a janela): a janela começa no
    dia seguinte ao último período carregado com sucesso;
  * horário comercial: a janela é reduzida aos últimos
    LIMITE_DIAS_HORARIO_COMERCIAL dias; a janela completa fica para a execução
    das 06h00. Carga completa em horário comercial é recusada.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterator

from .config import Config


@dataclass
class Janela:
    inicio: date
    fim: date            # inclusivo
    observacao: str = ""

    @property
    def dias(self) -> int:
        return (self.fim - self.inicio).days + 1


def em_horario_comercial(cfg: Config, agora: datetime | None = None) -> bool:
    agora = agora or datetime.now()
    ini, fim = cfg.horario_comercial
    return ini <= agora.time() <= fim


def calcular(cfg: Config, modo: str, data_ref: date, ultimo_fim_ok: date | None,
             inicio: date | None = None, fim: date | None = None,
             ignorar_horario: bool = False, agora: datetime | None = None) -> Janela | None:
    ontem = data_ref - timedelta(days=1)
    teto = min(ontem, cfg.periodo_fim) if cfg.periodo_fim else ontem
    obs = []

    if modo == "completo":
        j = Janela(inicio or cfg.periodo_inicio, fim or teto, "carga completa solicitada")
        if em_horario_comercial(cfg, agora) and not ignorar_horario and j.dias > cfg.limite_dias_horario_comercial:
            raise PermissionError(
                f"Carga completa de {j.dias} dias recusada em horário comercial "
                f"({cfg.horario_comercial[0]}-{cfg.horario_comercial[1]}). "
                "Agende fora do horário ou use --ignorar-horario conscientemente.")
        return j if j.inicio <= j.fim else None

    ini = data_ref - timedelta(days=cfg.janela_dias)
    recuperacao = False
    if ultimo_fim_ok is None:
        ini, recuperacao = cfg.periodo_inicio, True
        obs.append("primeira carga: desde o início do período")
    elif ultimo_fim_ok + timedelta(days=1) < ini:
        ini, recuperacao = ultimo_fim_ok + timedelta(days=1), True
        obs.append(f"buraco desde {ultimo_fim_ok}: janela estendida")
    ini = max(ini, cfg.periodo_inicio)

    if em_horario_comercial(cfg, agora) and not ignorar_horario:
        if recuperacao and (teto - ini).days + 1 > cfg.limite_dias_horario_comercial:
            # reduzir aqui deixaria o buraco para trás; melhor esperar a janela noturna
            raise PermissionError("Carga inicial/recuperação de buraco adiada: horário comercial")
        limite = teto - timedelta(days=cfg.limite_dias_horario_comercial - 1)
        if ini < limite:
            ini = limite
            obs.append(f"horário comercial: janela reduzida a {cfg.limite_dias_horario_comercial} dias")

    if ini > teto:
        return None
    return Janela(ini, teto, "; ".join(obs) or f"janela móvel de {cfg.janela_dias} dias")


def blocos(j: Janela, tamanho: int) -> Iterator[tuple[date, date]]:
    """Divide a janela em blocos [ini, fim_exclusivo) para consultas menores no Oracle."""
    atual = j.inicio
    while atual <= j.fim:
        prox = min(atual + timedelta(days=tamanho), j.fim + timedelta(days=1))
        yield atual, prox
        atual = prox
