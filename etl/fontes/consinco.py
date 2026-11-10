"""Acesso à Consinco (Oracle) — e um substituto fictício para testes.

As consultas ficam em sql/extracao/*.sql (versionadas, legíveis pelo DBA).
Cada consulta devolve colunas com os aliases do "contrato" descrito no
cabeçalho do arquivo .sql; o resto do ETL só conhece esses aliases.

Cuidados com a produção:
  * usuário somente leitura; o código nunca faz COMMIT no Oracle;
  * bind variables (plano reaproveitado, sem SQL injection);
  * call_timeout: uma consulta não fica presa indefinidamente;
  * module/action/client_identifier: o DBA identifica a sessão no V$SESSION;
  * arraysize alto: menos idas e voltas pela rede.
"""
from __future__ import annotations

import csv
import logging
import os
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Protocol

from ..config import RAIZ, Config

log = logging.getLogger("consinco")
PASTA_SQL = RAIZ / "sql" / "extracao"

ARQUIVOS = {
    "lojas": "01_lojas.sql",
    "produtos": "02_produtos.sql",
    "produto_codigo": "03_produto_codigo.sql",
    "avarias": "04_avarias.sql",
    "vendas": "05_vendas.sql",
    "produto_por_codigo": "07_produto_por_codigo.sql",
}


def expandir_listas(sql: str, listas: dict[str, Iterable[Any]]) -> tuple[str, dict[str, Any]]:
    """Troca ':categorias' por ':categorias_0, :categorias_1, ...' e devolve os binds."""
    binds: dict[str, Any] = {}
    for nome, valores in listas.items():
        valores = list(valores)
        if not valores:
            raise ValueError(f"Lista vazia para :{nome}")
        nomes = [f"{nome}_{i}" for i in range(len(valores))]
        sql = re.sub(rf":{nome}\b", ", ".join(f":{n}" for n in nomes), sql)
        binds.update(zip(nomes, valores))
    return sql, binds


class FonteConsinco(Protocol):
    def consultar(self, nome: str, params: dict[str, Any] | None = None,
                  listas: dict[str, Iterable[Any]] | None = None) -> list[dict[str, Any]]: ...
    def close(self) -> None: ...


class ConsincoOracle:
    def __init__(self, cfg: Config):
        import oracledb  # modo thin: não exige Oracle Instant Client

        if not (cfg.oracle_user and cfg.oracle_password and cfg.oracle_dsn):
            raise RuntimeError("Credenciais do Oracle ausentes (ORACLE_USER/ORACLE_PASSWORD/ORACLE_DSN)")
        self.con = oracledb.connect(user=cfg.oracle_user, password=cfg.oracle_password, dsn=cfg.oracle_dsn)
        self.con.call_timeout = cfg.oracle_timeout_ms
        self.con.module = "ETL_PREVENCAO_PERDAS"
        self.con.client_identifier = "etl_prevencao_perdas"
        if cfg.oracle_schema:
            # as consultas não levam o dono das tabelas (CONSINCO.MAX_EMPRESA): a sessão
            # aponta para o schema, como o DBeaver faz ao escolher o schema padrão
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_$#]{0,127}", cfg.oracle_schema):
                raise ValueError(f"ORACLE_SCHEMA inválido: {cfg.oracle_schema!r}")
            self.con.current_schema = cfg.oracle_schema.upper()
        # o endereço do servidor não vai para o log: o log pode ser enviado a terceiros
        log.info("Conectado ao Oracle %s | usuário %s | schema %s",
                 self.con.version, cfg.oracle_user.upper(), (cfg.oracle_schema or cfg.oracle_user).upper())

    def consultar(self, nome, params=None, listas=None):
        sql = (PASTA_SQL / ARQUIVOS[nome]).read_text(encoding="utf-8")
        sql, binds = expandir_listas(sql, listas or {})
        binds.update(params or {})
        # só passa os binds que a consulta realmente usa (o Oracle rejeita binds sobrando)
        usados = set(re.findall(r":(\w+)", re.sub(r"--[^\n]*", "", sql)))
        binds = {k: v for k, v in binds.items() if k in usados}
        cur = self.con.cursor()
        cur.arraysize = 5000
        cur.prefetchrows = 5000
        self.con.action = nome
        cur.execute(sql, binds)
        colunas = [d[0].lower() for d in cur.description]
        linhas = [dict(zip(colunas, r)) for r in cur]
        cur.close()
        return linhas

    def close(self):
        self.con.close()


class ConsincoFicticia:
    """Lê CSVs de tests/dados_ficticios simulando as saídas das consultas.

    Serve para testar o ETL de ponta a ponta sem acesso à produção. Com
    MOCK_FALHAR=1 simula a Consinco fora do ar (teste de falha controlada).
    """
    DATAS = {"avarias": "dta_lancamento", "vendas": "dta_venda"}

    def __init__(self, cfg: Config):
        if os.getenv("MOCK_FALHAR") == "1":
            raise ConnectionError("ORA-12541: TNS:no listener (simulado)")
        self.pasta: Path = cfg.mock_dir
        log.info("Consinco FICTÍCIA: lendo %s", self.pasta)

    def _ler(self, nome: str) -> list[dict[str, Any]]:
        with open(self.pasta / f"{nome}.csv", encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
        for l in linhas:
            for k, v in l.items():
                if v == "":
                    l[k] = None
                elif k.startswith(("dta_",)):
                    l[k] = datetime.fromisoformat(v)
                elif k.startswith(("vlr_", "qtd_")):
                    l[k] = Decimal(v)
                elif k.startswith(("nro_", "seq_", "cgo")):
                    l[k] = int(v)
        return linhas

    def consultar(self, nome, params=None, listas=None):
        params, listas = params or {}, listas or {}
        if nome == "produto_por_codigo":
            alvo = set(int(c) for c in listas["codigos"])
            return [l for l in self._ler("produtos_todos") if l["seq_produto"] in alvo]
        linhas = self._ler(nome)
        if "categorias" in listas and linhas and "seq_categoria" in linhas[0]:
            cats = set(listas["categorias"])
            linhas = [l for l in linhas if l["seq_categoria"] in cats]
        if nome in self.DATAS:
            col, ini, fim = self.DATAS[nome], params["dt_ini"], params["dt_fim"]
            linhas = [l for l in linhas if ini <= l[col].date() < fim]
        return linhas

    def close(self):
        pass


def conectar(cfg: Config) -> FonteConsinco:
    return ConsincoFicticia(cfg) if cfg.consinco_modo == "mock" else ConsincoOracle(cfg)
