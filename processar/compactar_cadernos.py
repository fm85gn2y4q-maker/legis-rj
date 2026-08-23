"""Compacta o texto dos cadernos, que é o que mais ocupa e o que mais comprime.

Os cadernos do Diário são texto puro de 300 KB a 1 MB cada, e comprimem cerca
de cinco para um. São 2,6 GB que viram uns 600 MB.

Por que não apagar: é o material bruto de onde os decretos saem, e o guia deste
projeto é claro — o que veio da rede fica intocado, porque a extração vai ser
refeita. Já foi refeita cinco vezes aqui.

Não toca em arquivo escrito nos últimos dez minutos: a coleta está rodando, e
comprimir algo que ainda está sendo escrito estraga os dois lados.
"""

from __future__ import annotations

import gzip
import pathlib
import shutil
import time

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PASTAS = [
    RAIZ / "dados" / "doerj" / "extras",
    RAIZ / "dados" / "doerj" / "cadernos",
    # As 4.454 edições diárias são o maior volume do acervo — 3,7 GB de texto
    # puro. É delas que os decretos saem, e a extração já foi refeita cinco
    # vezes: apagar está fora de questão, comprimir não custa nada.
    RAIZ / "dados" / "doerj",
]
DESCANSO = 600  # segundos desde a última escrita


def main() -> None:
    agora = time.time()
    ganho = 0
    feitos = pulados = 0
    for pasta in PASTAS:
        if not pasta.exists():
            continue
        for txt in sorted(pasta.glob("*.txt")):
            if agora - txt.stat().st_mtime < DESCANSO:
                pulados += 1
                continue
            destino = txt.with_suffix(".txt.gz")
            antes = txt.stat().st_size
            with txt.open("rb") as entrada, gzip.open(destino, "wb", 6) as saida:
                shutil.copyfileobj(entrada, saida)
            # Só apaga depois de conferir que o compactado abre e tem conteúdo.
            with gzip.open(destino, "rt", encoding="utf-8", errors="replace") as f:
                if len(f.read(2000)) < 100:
                    destino.unlink()
                    print(f"  {txt.name}: compactado saiu vazio; original mantido")
                    continue
            txt.unlink()
            ganho += antes - destino.stat().st_size
            feitos += 1
            if feitos % 200 == 0:
                print(f"  {feitos} compactados, {ganho / 1e9:.2f} GB liberados", flush=True)

    print(f"\n{feitos} compactados, {pulados} pulados (recém-escritos)")
    print(f"liberado: {ganho / 1e9:.2f} GB")


if __name__ == "__main__":
    main()
