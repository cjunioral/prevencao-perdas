"""Registro de execuções, cargas e rejeitados (schema controle).

O controle usa uma conexão própria em autocommit: o registro de uma carga que
FALHOU precisa ficar gravado mesmo quando a transação de dados sofre rollback.
Já os rejeitados são gravados na MESMA transação dos dados (gravar_rejeitados),
para que dado carregado e rejeitado sejam sempre consistentes entre si.
"""
from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import psycopg
from psycopg.types.json import Jsonb


@dataclass
class Rejeitado:
    linha_origem: int | None
    registro_original: dict[str, Any]
    motivo: str
    detalhe: str | None = None


@dataclass
class ResultadoCarga:
    lidas: int = 0
    carregadas: int = 0
    rejeitadas: int = 0
    inseridas: int = 0
    atualizadas: int = 0
    removidas: int = 0
    avisos: dict[str, int] = field(default_factory=dict)

    def resumo(self) -> str:
        return (f"lidas={self.lidas} carregadas={self.carregadas} rejeitadas={self.rejeitadas} "
                f"| analítico: +{self.inseridas} ~{self.atualizadas} -{self.removidas}")


def _json_default(v: Any) -> str:
    return str(v)


def jsonb(d: dict[str, Any]) -> Jsonb:
    return Jsonb(json.loads(json.dumps(d, default=_json_default, ensure_ascii=False)))


class Controle:
    def __init__(self, dsn: str):
        self.con = psycopg.connect(dsn, autocommit=True)

    def close(self) -> None:
        self.con.close()

    # ---------------- execução ----------------
    def iniciar_execucao(self, modo: str, data_ref: date, parametros: dict) -> int:
        return self.con.execute(
            """INSERT INTO controle.execucao (modo, data_referencia, host, pid, parametros)
               VALUES (%s, %s, %s, %s, %s) RETURNING id_execucao""",
            (modo, data_ref, socket.gethostname(), os.getpid(), jsonb(parametros)),
        ).fetchone()[0]

    def finalizar_execucao(self, id_execucao: int, status: str, mensagem: str | None = None) -> None:
        self.con.execute(
            "UPDATE controle.execucao SET fim = now(), status = %s, mensagem = %s WHERE id_execucao = %s",
            (status, mensagem, id_execucao))

    # ---------------- carga ----------------
    def iniciar_carga(self, id_execucao: int, fonte: str, *, arquivo: str | None = None,
                      aba: str | None = None, hash_arquivo: str | None = None,
                      periodo_inicio: date | None = None, periodo_fim: date | None = None) -> int:
        return self.con.execute(
            """INSERT INTO controle.carga (id_execucao, fonte, arquivo, aba, hash_arquivo,
                                           periodo_inicio, periodo_fim)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id_carga""",
            (id_execucao, fonte, arquivo, aba, hash_arquivo, periodo_inicio, periodo_fim),
        ).fetchone()[0]

    def finalizar_carga(self, id_carga: int, status: str, r: ResultadoCarga | None = None,
                        mensagem: str | None = None) -> None:
        r = r or ResultadoCarga()
        self.con.execute(
            """UPDATE controle.carga SET fim = now(), status = %s, linhas_lidas = %s,
                      linhas_carregadas = %s, linhas_rejeitadas = %s, linhas_inseridas = %s,
                      linhas_atualizadas = %s, linhas_removidas = %s, avisos = %s, mensagem = %s
               WHERE id_carga = %s""",
            (status, r.lidas, r.carregadas, r.rejeitadas, r.inseridas, r.atualizadas,
             r.removidas, jsonb(r.avisos) if r.avisos else None, mensagem, id_carga))

    def ultimo_hash_sucesso(self, fonte: str, aba: str) -> str | None:
        row = self.con.execute(
            """SELECT hash_arquivo FROM controle.carga
               WHERE fonte = %s AND aba = %s AND status = 'SUCESSO'
               ORDER BY inicio DESC LIMIT 1""", (fonte, aba)).fetchone()
        return row[0] if row else None

    def ultimo_fim_sucesso(self, fonte: str, inicio_periodo: date) -> date | None:
        """Último dia da cobertura CONTÍNUA desde inicio_periodo (None = nunca cobriu o início).

        Não basta o MAX(periodo_fim): uma carga manual de um dia isolado (ex.: teste de
        08/11) teria sucesso e esconderia setembro e outubro, que nunca foram carregados.
        Aqui os períodos com sucesso são unidos a partir do início; o primeiro buraco encerra
        a cobertura, e a próxima carga diária recomeça dali.
        """
        rows = self.con.execute(
            """SELECT periodo_inicio, periodo_fim FROM controle.carga
                WHERE fonte = %s AND status = 'SUCESSO' AND periodo_inicio IS NOT NULL
                ORDER BY periodo_inicio""", (fonte,)).fetchall()
        coberto: date | None = None
        for ini, fim in rows:
            limite = inicio_periodo if coberto is None else coberto + timedelta(days=1)
            if ini > limite:
                break
            if coberto is None or fim > coberto:
                coberto = fim
        return coberto


def gravar_rejeitados(cur: psycopg.Cursor, id_carga: int, fonte: str, rejeitados: list[Rejeitado],
                      arquivo: str | None = None, aba: str | None = None) -> None:
    if not rejeitados:
        return
    with cur.copy("""COPY controle.rejeitado (id_carga, fonte, arquivo, aba, linha_origem,
                                               registro_original, motivo, detalhe) FROM STDIN""") as cp:
        for r in rejeitados:
            cp.write_row((id_carga, fonte, arquivo, aba, r.linha_origem,
                          json.dumps(r.registro_original, default=_json_default, ensure_ascii=False),
                          r.motivo, r.detalhe))
