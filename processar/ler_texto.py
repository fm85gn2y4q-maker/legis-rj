"""Lê texto de edição do Diário, compactado ou não.

O acervo tem 3,7 GB de texto puro e o disco da máquina está apertado, então os
arquivos vão para gzip. Quem lê não precisa saber em que estado eles estão —
e é isso que este módulo garante, para a decisão de comprimir não vazar para
dentro de cada extrator.
"""

from __future__ import annotations

import gzip
import pathlib


def ler(caminho: pathlib.Path) -> str:
    if caminho.suffix == ".gz":
        with gzip.open(caminho, "rt", encoding="utf-8", errors="replace") as f:
            return f.read()
    return caminho.read_text(encoding="utf-8", errors="replace")


def edicoes(pasta: pathlib.Path) -> list[pathlib.Path]:
    """Todas as edições da pasta, em ordem, compactadas ou não."""
    return sorted(
        list(pasta.glob("*.txt")) + list(pasta.glob("*.txt.gz")),
        key=lambda p: p.name,
    )


def dia_de(caminho: pathlib.Path) -> str:
    """A data está no começo do nome, com ou sem as extensões."""
    return caminho.name[:10]
