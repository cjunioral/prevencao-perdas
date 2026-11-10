"""Impede duas execuções simultâneas (diferencial da Etapa 3).

Usa um advisory lock do PostgreSQL, mantido por uma conexão dedicada durante
toda a execução. Vantagens sobre um arquivo .lock:
  * se o processo morrer (queda de energia, kill), a conexão cai e o
    PostgreSQL libera a trava sozinho — não sobra trava "órfã";
  * vale para qualquer máquina que rode o processo contra o mesmo banco.
A segunda execução não espera: registra que foi BLOQUEADA e sai.
Além disso, cada fonte grava numa transação única, então mesmo sem a trava
nenhum leitor veria dados pela metade.
"""
from __future__ import annotations

import psycopg

CHAVE_TRAVA = 742_001  # identificador arbitrário e fixo deste processo


class Trava:
    def __init__(self, dsn: str):
        self.con = psycopg.connect(dsn, autocommit=True)
        self.obtida = False

    def __enter__(self) -> "Trava":
        self.obtida = self.con.execute("SELECT pg_try_advisory_lock(%s)", (CHAVE_TRAVA,)).fetchone()[0]
        return self

    def __exit__(self, *exc) -> None:
        if self.obtida:
            self.con.execute("SELECT pg_advisory_unlock(%s)", (CHAVE_TRAVA,))
        self.con.close()
