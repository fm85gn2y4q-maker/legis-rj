"""Fica esperando a coleta da ALERJ fechar, e sai quando fechar.

Não coleta nada: só olha o disco de dois em dois minutos. Serve para avisar —
sai com código 0 no minuto em que as duas fases terminam, e imprime o resumo.

As duas condições, e as duas precisam valer:

  1. a varredura chegou ao último número da maior série;
  2. todo ato do índice tem documento em disco.

Só a primeira já valeu antes com a fase B pela metade — a fase A termina e a B
mal começou. Quem parar na primeira anuncia fim que não houve.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from coletar_alerj import MAIOR_NUMERO  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados" / "alerj"
INTERVALO = 120


def estado() -> tuple[int, int, int]:
    progresso = json.loads((DADOS / "progresso.json").read_text("utf-8"))
    unids = {
        json.loads(l)["unid"]
        for l in (DADOS / "indice.jsonl").read_text("utf-8").splitlines()
        if l.strip()
    }
    baixados = {p.stem for p in (DADOS / "docs").glob("*.html")}
    return progresso.get("ultimo_numero", 0), len(unids), len(baixados & unids)


def main() -> None:
    while True:
        numero, no_indice, com_documento = estado()
        if numero >= MAIOR_NUMERO and com_documento >= no_indice:
            print(
                f"ALERJ CONCLUÍDA — {no_indice} atos no índice, "
                f"{com_documento} documentos em disco",
                flush=True,
            )
            return
        print(
            f"{time.strftime('%H:%M')}  número {numero}/{MAIOR_NUMERO} · "
            f"documentos {com_documento}/{no_indice}",
            flush=True,
        )
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
