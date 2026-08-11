"""Colhe a situação das espécies cujo documento não a declara.

O DEFEITO QUE ISTO CORRIGE

No documento de uma lei ordinária, a situação vem entre colchetes: `Texto da
Lei [ Em Vigor ]`. Na lei complementar, na emenda e no decreto legislativo o
colchete vem **vazio** — `Texto da Resolução [ ]`. Medido: 100 de 100 emendas,
252 de 252 decretos legislativos, 234 de 234 leis complementares e 1.015
resoluções, todas sem situação nenhuma no documento.

Sem tratar isso, o acervo responderia sobre lei complementar sem qualquer
informação de vigência — e o silêncio se confunde com "em vigor" na cabeça de
quem lê.

A situação existe: está na **linha da listagem** da busca, na coluna Status, e
a coleta a descartava porque só guardava o link. Aqui ela é colhida e gravada
à parte, para o banco cruzar por identificador.

Ficam também número, ano, ementa e autoria da listagem — servem de segunda
opinião sobre o que se leu do documento.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from alerj import BASE, Alerj, _decodifica_bytes  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ALERJ = RAIZ / "dados" / "alerj"
SAIDA = ALERJ / "situacao_especies.jsonl"
ESPECIES = RAIZ / "medicoes" / "especies.json"

ANOS = range(1975, 2027)
CONSULTA_AMPLA = "de"
TETO = 1_000
NAO_COLETAR = {"geral", "lei_ordinaria"}

# Valores vistos na coluna Status. Serve para não confundir ementa com situação
# quando a tabela vier com uma coluna a menos.
SITUACOES = {
    "em vigor",
    "revogado",
    "revogada",
    "declarado inconstitucional",
    "declarada inconstitucional",
    "em vigor com alterações",
    "suspenso",
    "suspensa",
    "declarado parcialmente inconstitucional",
    "declarada parcialmente inconstitucional",
    "trabalhando o texto",
}


def linhas_da_busca(a: Alerj, view: str, consulta: str) -> dict[str, dict]:
    resp = a._pedir(
        "POST",
        f"{BASE}/{view}?SearchView",
        data={"Query": consulta, "SearchOrder": "1", "SearchMax": "0"},
    )
    sopa = BeautifulSoup(_decodifica_bytes(resp.content), "html.parser")
    achados: dict[str, dict] = {}
    for tr in sopa.find_all("tr"):
        link = tr.find("a", href=re.compile("OpenDocument", re.IGNORECASE))
        if not link:
            continue
        unid = re.search(r"/([0-9a-f]{32})\?OpenDocument", link.get("href", ""))
        if not unid:
            continue
        celulas = [
            " ".join(td.get_text(" ", strip=True).split()) for td in tr.find_all("td")
        ]
        celulas = [c for c in celulas if c]
        situacao = next(
            (c for c in celulas if c.strip().lower() in SITUACOES), ""
        )
        achados[unid.group(1)] = {
            "unid": unid.group(1),
            "numero_na_listagem": celulas[0] if celulas else "",
            "ano_na_listagem": celulas[1] if len(celulas) > 1 else "",
            "situacao_na_listagem": situacao,
            "colunas": celulas,
        }
    return achados


def main() -> None:
    especies = json.loads(ESPECIES.read_text("utf-8"))
    a = Alerj(pausa=1.2)
    colhidos: dict[str, dict] = {}

    for especie, dados in especies.items():
        if especie in NAO_COLETAR or not dados.get("view"):
            continue
        view = dados["view"]
        achados = linhas_da_busca(a, view, CONSULTA_AMPLA)
        if len(achados) >= TETO:
            print(f"{especie}: ampla no teto; por ano", flush=True)
            for ano in ANOS:
                try:
                    achados.update(linhas_da_busca(a, view, str(ano)))
                except Exception as exc:  # noqa: BLE001
                    print(f"   {ano}: {type(exc).__name__}", flush=True)
                if ano % 10 == 0:
                    print(f"   [{ano}] {len(achados)}", flush=True)
        com_situacao = sum(1 for v in achados.values() if v["situacao_na_listagem"])
        print(
            f"{especie}: {len(achados)} linhas, {com_situacao} com situação",
            flush=True,
        )
        for unid, reg in achados.items():
            reg["especie_da_view"] = especie
            colhidos[unid] = reg

    with SAIDA.open("w", encoding="utf-8") as f:
        for reg in colhidos.values():
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    print(f"\n{len(colhidos)} registros em {SAIDA}")


if __name__ == "__main__":
    main()
