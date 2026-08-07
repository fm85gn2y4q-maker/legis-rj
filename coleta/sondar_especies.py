"""Descobre o formulário de busca de CADA espécie normativa.

A coleta inteira da ALERJ passou por um formulário só, e ele é o das **leis
ordinárias**. Medido depois de 11.123 atos coletados: todos os resultados vêm
da view `c8aa0900…`, e todos os documentos baixados se identificam como "Lei
Ordinária". Lei complementar, emenda constitucional, decreto legislativo e
resolução ficaram inteiramente de fora.

Não é erro de busca: no Domino, `$searchForm` pertence à view de onde se
partiu, e a pesquisa não sai dela. Uma consulta por `"lei complementar"`
devolve 506 resultados — todos leis ordinárias que *mencionam* lei
complementar. O vocabulário engana; o metadado não.

Este script vai a cada formulário de espécie, lê a view a que ele pertence e o
documento de busca correspondente. É o que falta para varrer o resto.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from alerj import BASE, VIEWS, Alerj  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def main() -> None:
    a = Alerj(pausa=1.5)
    achados = {}
    for especie, formulario in VIEWS.items():
        try:
            html = a.view(formulario)
        except Exception as exc:  # noqa: BLE001
            achados[especie] = {"erro": str(exc)[:120]}
            print(f"{especie:<24} erro: {exc}")
            continue

        view = re.search(r"/contlei\.nsf/([0-9a-f]{32})/\$searchForm", html)
        if not view:
            achados[especie] = {"formulario": formulario, "view": None}
            print(f"{especie:<24} sem link de busca")
            continue

        # A página do $searchForm traz o POST que executa a pesquisa. Vale
        # tolerar falha aqui: a coleta está rodando contra o mesmo servidor, e
        # perder uma espécie não pode derrubar a sondagem das outras.
        try:
            pagina = a.documento(f"{BASE}/{view.group(1)}/$searchForm?SearchView")
        except Exception as exc:  # noqa: BLE001
            achados[especie] = {
                "formulario": formulario,
                "view": view.group(1),
                "erro_busca": str(exc)[:120],
            }
            print(f"{especie:<24} view {view.group(1)[:12]}…  busca: {exc}"[:110])
            continue
        acao = re.search(r'action="/contlei\.nsf/([0-9a-f]{32})\?CreateDocument"', pagina)
        achados[especie] = {
            "formulario": formulario,
            "view": view.group(1),
            "busca": acao.group(1) if acao else None,
        }
        print(
            f"{especie:<24} view {view.group(1)[:12]}…  "
            f"busca {(acao.group(1)[:12] + '…') if acao else '—'}"
        )

    destino = RAIZ / "medicoes" / "especies.json"
    destino.write_text(json.dumps(achados, ensure_ascii=False, indent=2), encoding="utf-8")
    buscas = {v.get("busca") for v in achados.values() if v.get("busca")}
    print(f"\nformulários de busca distintos: {len(buscas)}")
    print(f"gravado em {destino}")


if __name__ == "__main__":
    main()
