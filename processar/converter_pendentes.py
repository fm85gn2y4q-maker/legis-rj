"""Converte os PDFs que ficaram sem texto — sem baixar nada de novo.

674 edições foram baixadas e nenhuma virou texto: o `pdftotext` não estava no
PATH da Tarefa Agendada, e cada uma falhou com FileNotFoundError enquanto a
coleta seguia adiante. Os arquivos estão em disco; o que falta é a conversão.

São 2,5 GB que não precisam ser baixados de novo — e é por isso que o PDF só é
apagado **depois** de a conversão dar certo.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "coleta"))

from ferramentas import PDFTOTEXT  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def main() -> None:
    pastas = [RAIZ / "dados" / "doerj" / "extras", RAIZ / "dados" / "doerj" / "cadernos"]
    pendentes = [
        p
        for pasta in pastas
        if pasta.exists()
        for p in sorted(pasta.glob("*.pdf"))
        if not p.with_suffix(".txt").exists()
    ]
    print(f"{len(pendentes)} PDFs sem texto")
    convertidos = falhos = 0
    for i, pdf in enumerate(pendentes, 1):
        try:
            subprocess.run(
                [PDFTOTEXT, "-enc", "UTF-8", str(pdf), str(pdf.with_suffix(".txt"))],
                check=True, capture_output=True, timeout=900,
            )
            pdf.unlink()
            convertidos += 1
        except Exception as exc:  # noqa: BLE001
            falhos += 1
            print(f"  {pdf.name}: {type(exc).__name__}", flush=True)
        if i % 100 == 0:
            print(f"  [{i}/{len(pendentes)}] {convertidos} ok, {falhos} falhos", flush=True)
    print(f"\n{convertidos} convertidos, {falhos} falhos")


if __name__ == "__main__":
    main()
