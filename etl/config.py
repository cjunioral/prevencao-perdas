"""Configuração lida de variáveis de ambiente / arquivo .env.

Nenhuma credencial fica no código. Copie .env.example para .env e preencha.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, time
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


def _env(nome: str, padrao: str | None = None, obrigatorio: bool = False) -> str:
    valor = os.getenv(nome, padrao)
    if obrigatorio and not valor:
        raise RuntimeError(f"Variável de ambiente obrigatória não definida: {nome}")
    return valor or ""


def _data(nome: str, padrao: str = "") -> date | None:
    v = _env(nome, padrao).strip()
    return date.fromisoformat(v) if v else None


def _categorias(texto: str) -> dict[int, str]:
    """'AÇOUGUE:101,HORTIFRUTI:202' -> {101: 'AÇOUGUE', 202: 'HORTIFRUTI'}"""
    mapa: dict[int, str] = {}
    for item in filter(None, (p.strip() for p in texto.split(","))):
        rotulo, codigo = item.split(":")
        mapa[int(codigo)] = rotulo.strip().upper()
    return mapa


def _horario(texto: str) -> tuple[time, time]:
    ini, fim = texto.split("-")
    return time.fromisoformat(ini.strip()), time.fromisoformat(fim.strip())


@dataclass(frozen=True)
class Config:
    # PostgreSQL analítico
    pg_host: str = field(default_factory=lambda: _env("PG_HOST", "localhost"))
    pg_port: int = field(default_factory=lambda: int(_env("PG_PORT", "5432")))
    pg_db: str = field(default_factory=lambda: _env("PG_DB", "prevencao_perdas"))
    pg_user: str = field(default_factory=lambda: _env("PG_USER", "postgres"))
    pg_password: str = field(default_factory=lambda: _env("PG_PASSWORD", ""))

    # Consinco (Oracle) — somente leitura
    consinco_modo: str = field(default_factory=lambda: _env("CONSINCO_MODO", "oracle"))  # oracle | mock
    oracle_user: str = field(default_factory=lambda: _env("ORACLE_USER"))
    oracle_password: str = field(default_factory=lambda: _env("ORACLE_PASSWORD"))
    oracle_dsn: str = field(default_factory=lambda: _env("ORACLE_DSN"))
    oracle_timeout_ms: int = field(default_factory=lambda: int(_env("ORACLE_TIMEOUT_MS", "600000")))
    mock_dir: Path = field(default_factory=lambda: RAIZ / _env("MOCK_DIR", "tests/dados_ficticios"))

    # Escopo do negócio
    periodo_inicio: date = field(default_factory=lambda: _data("PERIODO_INICIO", "2026-09-01"))
    periodo_fim: date | None = field(default_factory=lambda: _data("PERIODO_FIM"))
    categorias: dict[int, str] = field(default_factory=lambda: _categorias(_env("CATEGORIAS_ESCOPO", obrigatorio=True)))
    nivel_categoria: int = field(default_factory=lambda: int(_env("NIVEL_CATEGORIA", "1")))
    cgos_avaria: tuple[int, ...] = field(default_factory=lambda: tuple(
        int(c) for c in _env("CGOS_AVARIA", "403,552").split(",") if c.strip()))

    # Carga incremental
    janela_dias: int = field(default_factory=lambda: int(_env("JANELA_RETROATIVA_DIAS", "40")))
    bloco_dias: int = field(default_factory=lambda: int(_env("BLOCO_EXTRACAO_DIAS", "7")))
    horario_comercial: tuple[time, time] = field(default_factory=lambda: _horario(_env("HORARIO_COMERCIAL", "07:30-21:00")))
    limite_dias_horario_comercial: int = field(default_factory=lambda: int(_env("LIMITE_DIAS_HORARIO_COMERCIAL", "3")))

    # Planilha
    pasta_entrada: Path = field(default_factory=lambda: RAIZ / _env("PASTA_ENTRADA", "entrada"))
    padrao_planilha: str = field(default_factory=lambda: _env("PADRAO_PLANILHA", "*.xls[xm]"))
    duplicidade: str = field(default_factory=lambda: _env("DUPLICIDADE_CONFLITANTE", "rejeitar"))  # rejeitar | somar

    pasta_logs: Path = field(default_factory=lambda: RAIZ / _env("PASTA_LOGS", "logs"))

    def dsn_pg(self, banco: str | None = None) -> str:
        return (f"host={self.pg_host} port={self.pg_port} dbname={banco or self.pg_db} "
                f"user={self.pg_user} password={self.pg_password} application_name=etl_prevencao_perdas")
