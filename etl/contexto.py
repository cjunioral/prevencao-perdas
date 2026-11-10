from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from .config import Config
from .controle import Controle
from .fontes.consinco import FonteConsinco, conectar


@dataclass
class Contexto:
    cfg: Config
    controle: Controle
    id_execucao: int
    data_ref: date
    _consinco: FonteConsinco | None = field(default=None, repr=False)
    _erro_consinco: Exception | None = field(default=None, repr=False)

    @property
    def consinco(self) -> FonteConsinco:
        """Conecta na primeira vez que alguém precisa. Se falhar, todas as
        fontes da Consinco recebem o mesmo erro, mas a planilha segue."""
        if self._erro_consinco:
            raise self._erro_consinco
        if self._consinco is None:
            try:
                self._consinco = conectar(self.cfg)
            except Exception as e:  # noqa: BLE001 — falha controlada
                self._erro_consinco = e
                logging.getLogger("consinco").error("Consinco indisponível: %s", e)
                raise
        return self._consinco

    def fechar(self) -> None:
        if self._consinco:
            self._consinco.close()
