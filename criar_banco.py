"""Cria o banco analítico do zero a partir de sql/ddl (um único comando).

    python criar_banco.py            # cria o banco (se não existir) e aplica a DDL
    python criar_banco.py --recriar  # APAGA e recria o banco (cuidado)

Os scripts de sql/ddl são aplicados em ordem alfabética, numa única transação:
ou o banco fica inteiro, ou nada muda. Todos são idempotentes (IF NOT EXISTS /
CREATE OR REPLACE), então rodar de novo não quebra nada.
"""
from __future__ import annotations

import argparse
import sys

import psycopg
from psycopg import sql

from etl.config import RAIZ, Config


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--recriar", action="store_true", help="apaga o banco antes de criar")
    args = p.parse_args()
    cfg = Config()

    with psycopg.connect(cfg.dsn_pg("postgres"), autocommit=True) as adm:
        existe = adm.execute("SELECT 1 FROM pg_database WHERE datname = %s", (cfg.pg_db,)).fetchone()
        if existe and args.recriar:
            print(f"Apagando banco {cfg.pg_db}...")
            adm.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(cfg.pg_db)))
            existe = None
        if not existe:
            print(f"Criando banco {cfg.pg_db}...")
            adm.execute(sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' TEMPLATE template0")
                        .format(sql.Identifier(cfg.pg_db)))

    scripts = sorted((RAIZ / "sql" / "ddl").glob("*.sql"))
    with psycopg.connect(cfg.dsn_pg()) as con:          # uma transação para tudo
        for s in scripts:
            print(f"  aplicando {s.name}")
            con.execute(s.read_text(encoding="utf-8"))
    print(f"Banco {cfg.pg_db} pronto ({len(scripts)} scripts aplicados).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
