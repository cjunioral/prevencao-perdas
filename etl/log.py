"""Log em console e em arquivo com a data no nome (logs/etl_AAAA-MM-DD.log)."""
from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path

FORMATO = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def configurar(pasta: Path, dia: date | None = None) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"etl_{(dia or date.today()).isoformat()}.log"
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.handlers.clear()
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(arquivo, encoding="utf-8")):
        h.setFormatter(logging.Formatter(FORMATO, "%Y-%m-%d %H:%M:%S"))
        raiz.addHandler(h)
    return arquivo
