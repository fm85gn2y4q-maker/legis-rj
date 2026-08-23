"""Os 312 decretos que a busca do Diário não acha: existem ou não existem?

Três explicações possíveis, e elas levam a acervos diferentes:

  a) o número nunca foi usado — a numeração pula, e não falta nada;
  b) o decreto saiu em Parte diferente da I, que é a que se coleta;
  c) o índice de texto do Diário não o alcança, e ele está lá.

Só (a) é inofensiva. Nas outras duas há decreto faltando, e o acervo precisa
dizer isso.

A prova mais barata está no próprio acervo: **um decreto que existiu é citado
por outros**. "Altera o Decreto nº 47.123" só se escreve se o 47.123 existir.
Uma passada pelos 3,7 GB de texto colhe todo número de decreto citado; o que
estiver lá existe, mesmo que a busca não o encontre.
"""

from __future__ import annotations

import collections
import json
import pathlib
import re

import ler_texto

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DOERJ = RAIZ / "dados" / "doerj"

# "Decreto nº 47.123", "DECRETO N° 47123", "decreto estadual nº 47.123"
CITACAO = re.compile(
    r"[Dd][Ee][Cc][Rr][Ee][Tt][Oo]\s+(?:[Ee]stadual\s+)?[Nn][ºo°.]{0,2}\s*(\d{2}\.?\d{3})\b"
)


def main() -> None:
    ausentes = set(json.loads((DOERJ / "decretos_sem_materia.json").read_text("utf-8")))
    citados: collections.Counter = collections.Counter()

    arquivos = ler_texto.edicoes(DOERJ)
    print(f"lendo {len(arquivos)} edições em busca de citações…")
    for i, caminho in enumerate(arquivos, 1):
        texto = ler_texto.ler(caminho)
        for achado in CITACAO.finditer(texto):
            numero = int(achado.group(1).replace(".", ""))
            if numero in ausentes:
                citados[numero] += 1
        if i % 1000 == 0:
            print(f"  {i}/{len(arquivos)} — {len(citados)} dos ausentes já citados", flush=True)

    print(f"\ndos {len(ausentes)} ausentes, {len(citados)} aparecem citados em outro ato")
    print(f"nunca citados: {len(ausentes) - len(citados)}")
    print("\nmais citados (existem, e a busca não os acha):")
    for numero, vezes in citados.most_common(8):
        print(f"   {numero}: citado {vezes}x")

    (RAIZ / "medicoes").mkdir(exist_ok=True)
    (RAIZ / "medicoes" / "ausentes_citados.json").write_text(
        json.dumps(
            {
                "ausentes": len(ausentes),
                "citados_em_outro_ato": len(citados),
                "nunca_citados": len(ausentes) - len(citados),
                "detalhe": dict(citados.most_common()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
