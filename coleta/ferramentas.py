r"""Onde estão os programas externos de que a coleta depende.

O `pdftotext` mora em `C:\Program Files\Git\mingw64\bin`, que entra no PATH
de um terminal do Git Bash e **não** entra no PATH da Tarefa Agendada. O
sintoma foi caro: 674 edições baixadas, 2,5 GB em disco e zero texto extraído,
com um `FileNotFoundError` por edição no log — e a coleta seguindo em frente
como se estivesse trabalhando.

Chamar pelo caminho absoluto tira o PATH da equação. A busca acontece uma vez,
na importação, e vale para quem rodar de onde for.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

_CANDIDATOS = (
    r"C:\Program Files\Git\mingw64\bin\pdftotext.exe",
    r"C:\Program Files\Xpdf\bin64\pdftotext.exe",
    r"C:\Program Files (x86)\Git\mingw64\bin\pdftotext.exe",
)


def _achar_pdftotext() -> str:
    do_ambiente = os.environ.get("PDFTOTEXT")
    if do_ambiente and Path(do_ambiente).exists():
        return do_ambiente
    no_path = shutil.which("pdftotext")
    if no_path:
        return no_path
    for caminho in _CANDIDATOS:
        if Path(caminho).exists():
            return caminho
    # Devolve o nome puro: quem chamar recebe o FileNotFoundError com a
    # mensagem clara, em vez de um erro obscuro mais adiante.
    return "pdftotext"


PDFTOTEXT = _achar_pdftotext()
