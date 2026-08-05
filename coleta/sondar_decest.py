"""Fase 1, parte 3 — a base de decretos do Executivo (`decest.nsf`).

Decreto do Governador não está em `contlei.nsf`: ali "Decreto" é decreto
legislativo, ato da própria Assembleia. A ALERJ mantém uma segunda base,
`decest.nsf`, com os decretos estaduais — e ela **não** aparece no menu do
portal, o que significa que ninguém garantiu que esteja atualizada. É a
primeira coisa a medir: até que decreto ela vai.

O formulário de busca aqui é o padrão do Domino (`?SearchView` com `Query` e
`SearchMax`), diferente do formulário desenhado da `contlei.nsf`.
"""

from __future__ import annotations

import json
import pathlib
import re

import requests
from bs4 import BeautifulSoup

BASE = "https://alerjln1.alerj.rj.gov.br/decest.nsf"
VIEW = "c8ea52144c8b5c950325654c00612d63"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36"

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def decodifica(cru: bytes) -> str:
    try:
        return cru.decode("utf-8")
    except UnicodeDecodeError:
        return cru.decode("iso-8859-1")


def buscar(sessao: requests.Session, query: str, maximo: str = "0") -> list[dict]:
    resp = sessao.post(
        f"{BASE}/{VIEW}?SearchView",
        data={"Query": query, "SearchOrder": "1", "SearchMax": maximo},
        timeout=180,
    )
    resp.raise_for_status()
    sopa = BeautifulSoup(decodifica(resp.content), "html.parser")
    linhas = []
    for tr in sopa.find_all("tr"):
        link = tr.find("a", href=re.compile("OpenDocument", re.IGNORECASE))
        if not link:
            continue
        celulas = [
            " ".join(td.get_text(" ", strip=True).split()) for td in tr.find_all("td")
        ]
        linhas.append({"href": link.get("href", ""), "colunas": [c for c in celulas if c]})
    return linhas


def main() -> None:
    sessao = requests.Session()
    sessao.headers["User-Agent"] = UA
    medicoes: dict[str, object] = {}

    print("[1] a view abre? o que traz por linha?")
    resp = sessao.get(f"{BASE}/{VIEW}?OpenView", timeout=120)
    sopa = BeautifulSoup(decodifica(resp.content), "html.parser")
    texto = " ".join(sopa.get_text(" ", strip=True).split())
    medicoes["view"] = texto[:800]
    print("   ", texto[:400])

    print("\n[2] volume e teto da busca")
    for termo in ["decreto", "governador", "estado"]:
        linhas = buscar(sessao, termo)
        medicoes[f"busca:{termo}"] = len(linhas)
        print(f"    Query={termo!r} SearchMax=0 -> {len(linhas)} documentos")
        if linhas:
            print(f"      1ª linha: {linhas[0]['colunas']}")

    print("\n[3] até onde vai a base (decreto mais recente localizável)")
    for numero in ["49.792", "48.313", "45.000", "40.000", "30.000", "10.000"]:
        linhas = buscar(sessao, f'"{numero}"', maximo="10")
        print(f"    {numero} -> {len(linhas)} ocorrências")
        medicoes[f"numero:{numero}"] = len(linhas)

    destino = RAIZ / "medicoes" / "decest.json"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(
        json.dumps(medicoes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\ngravado em {destino}")


if __name__ == "__main__":
    main()
