"""Fase 1 do extrator de decretos — como o ato aparece no texto do Diário.

A pergunta que decide tudo, de novo: **o que é um registro aqui?** Uma edição
não é um decreto: é dezenas de atos emendados num texto só, e delimitar errado
não dá erro — dá um decreto com o texto do vizinho.

O primeiro olhar já mostrou duas coisas com o mesmo rótulo:

    DECRETO Nº 48.309 DE 09 DE JANEIRO DE 2023     ← normativo, numerado
    DECRETO DE 09 DE JANEIRO DE 2023               ← de pessoal, sem número

O segundo é nomeação e exoneração, e é a maioria em volume. Confundir os dois
enche o acervo de atos que ninguém cita e afunda os que se citam.
"""

from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DOERJ = RAIZ / "dados" / "doerj"

# Começo de linha, porque no meio da linha é citação. Ver o guia: cabeçalho e
# citação têm a mesma forma, e a posição é o que os separa.
COM_NUMERO = re.compile(
    r"^DECRETO\s+N[ºO°]?\s*([\d.]+)\s+DE\s+(\d{1,2})\s+DE\s+([A-ZÇÃÉ]+)\s+DE\s+(\d{4})",
    re.MULTILINE,
)
SEM_NUMERO = re.compile(
    r"^DECRETOS?\s+DE\s+\d{1,2}\s+DE\s+[A-ZÇÃÉ]+\s+DE\s+\d{4}", re.MULTILINE
)
QUALQUER = re.compile(r"^DECRETO[S]?[- ]?[A-ZÇ]*", re.MULTILINE)


def main() -> None:
    arquivos = sorted(DOERJ.glob("*.txt"))
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else len(arquivos)
    arquivos = arquivos[:limite]
    print(f"{len(arquivos)} edições")

    numerados: dict[str, list[str]] = collections.defaultdict(list)
    sem_numero = 0
    rotulos = collections.Counter()
    por_ano = collections.Counter()

    for i, caminho in enumerate(arquivos, 1):
        texto = caminho.read_text(encoding="utf-8", errors="replace")
        for achado in COM_NUMERO.finditer(texto):
            numero = achado.group(1).replace(".", "")
            numerados[numero].append(caminho.stem)
            por_ano[achado.group(4)] += 1
        sem_numero += len(SEM_NUMERO.findall(texto))
        for r in QUALQUER.findall(texto):
            rotulos[" ".join(r.split())] += 1
        if i % 500 == 0:
            print(f"  {i}/{len(arquivos)} — {len(numerados)} números distintos", flush=True)

    print(f"\ndecretos numerados: {sum(len(v) for v in numerados.values())} ocorrências, "
          f"{len(numerados)} números distintos")
    print(f"cabeçalhos sem número (pessoal): {sem_numero}")

    inteiros = sorted(int(n) for n in numerados if n.isdigit())
    if inteiros:
        print(f"faixa de números: {inteiros[0]} a {inteiros[-1]}")
        buracos = [n for n in range(inteiros[0], inteiros[-1] + 1) if n not in set(inteiros)]
        print(f"buracos na série: {len(buracos)}")

    print("\n--- rótulos que começam linha ---")
    for rotulo, n in rotulos.most_common(12):
        print(f"{n:>8}  {rotulo}")

    print("\n--- decretos numerados por ano ---")
    for ano in sorted(por_ano):
        print(f"  {ano}: {por_ano[ano]}")

    repetidos = {n: e for n, e in numerados.items() if len(e) > 1}
    print(f"\nnúmeros que aparecem em mais de uma edição: {len(repetidos)}")
    for numero, edicoes in list(repetidos.items())[:5]:
        print(f"  {numero}: {edicoes[:4]}")

    (RAIZ / "medicoes").mkdir(exist_ok=True)
    (RAIZ / "medicoes" / "decretos_doerj.json").write_text(
        json.dumps(
            {
                "edicoes_lidas": len(arquivos),
                "numeros_distintos": len(numerados),
                "ocorrencias": sum(len(v) for v in numerados.values()),
                "sem_numero": sem_numero,
                "por_ano": dict(sorted(por_ano.items())),
                "repetidos": len(repetidos),
                "rotulos": rotulos.most_common(20),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
