"""Fase 1, parte 4 — o topo de cada série.

Serve a uma pergunta só, e ela é de cobertura: **até onde cada base vai?**
Sem isso não se sabe se a coleta terminou nem se a base da ALERJ acompanha o
que o Executivo publicou ontem no Diário Oficial.

As views trazem as 15 linhas mais recentes de cada espécie — e como não há
paginação (ver alerj.py), essas 15 são exatamente o que dá para ler sem busca.
É pouco, mas responde o topo, que é o que se quer aqui.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from alerj import VIEWS, Alerj  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def linhas_da_view(html: str) -> list[list[str]]:
    sopa = BeautifulSoup(html, "html.parser")
    saida = []
    for tr in sopa.find_all("tr"):
        if not tr.find("a", href=re.compile("OpenDocument", re.IGNORECASE)):
            continue
        celulas = [
            " ".join(td.get_text(" ", strip=True).split()) for td in tr.find_all("td")
        ]
        celulas = [c for c in celulas if c]
        if celulas:
            saida.append(celulas)
    return saida


def main() -> None:
    a = Alerj(pausa=1.5)
    inventario: dict[str, object] = {}

    for especie, view in VIEWS.items():
        try:
            linhas = linhas_da_view(a.view(view))
        except Exception as exc:  # noqa: BLE001
            inventario[especie] = {"erro": str(exc)}
            print(f"{especie:<24} erro: {exc}")
            continue
        topo = linhas[0] if linhas else []
        inventario[especie] = {
            "view": view,
            "linhas_visiveis": len(linhas),
            "mais_recente": topo,
        }
        print(f"{especie:<24} {len(linhas):>3} linhas | topo: {topo[:3]}")

    destino = RAIZ / "medicoes" / "inventario.json"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(
        json.dumps(inventario, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\ngravado em {destino}")


if __name__ == "__main__":
    main()
