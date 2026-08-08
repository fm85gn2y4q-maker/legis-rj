"""Coleta as espécies que a varredura por número deixou de fora.

O QUE ACONTECEU, E POR QUE NÃO FOI ERRO DE BUSCA

A coleta da ALERJ passou inteira por um formulário só, e ele é o das leis
ordinárias. Medido depois de 11.123 atos: **todos** os resultados vêm da view
`c8aa0900…` e todos os documentos se identificam como "Lei Ordinária". Lei
complementar, emenda constitucional, decreto legislativo e resolução ficaram
fora — cerca de 2.800 atos, entre eles as leis complementares.

O que enganou: uma consulta por `"lei complementar"` devolve 506 resultados, e
todos são leis ordinárias que *mencionam* lei complementar. O vocabulário não
distingue espécie; o metadado distingue. Foi o que a contagem por view mostrou,
e nenhuma leitura de texto teria mostrado.

O CAMINHO QUE FUNCIONA

Cada espécie tem sua própria view, e a busca padrão do Domino — `POST` em
`/contlei.nsf/<view>?SearchView` — pesquisa **dentro** dela. É outro mecanismo
que o formulário desenhado das leis ordinárias, e é o mesmo que já se usava na
base de decretos.

Duas estratégias, escolhidas pelo tamanho da espécie:

- **Espécie pequena**: uma consulta ampla basta. Medido: `de` devolve 234 na
  lei complementar, 100 na emenda, 252 no decreto legislativo — números que
  batem com o topo de cada série, e portanto são o acervo inteiro.
- **Espécie grande**: `de` bate no teto de 1.000 (resolução e "gerais"), e aí
  volta a varredura por número, que é o que cabe no teto.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from alerj import BASE, Alerj, _decodifica_bytes  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "dados" / "alerj"
DOCS = SAIDA / "docs"
INDICE = SAIDA / "indice_especies.jsonl"
PROGRESSO = SAIDA / "progresso_especies.json"
ESPECIES = RAIZ / "medicoes" / "especies.json"

TETO = 1_000
CONSULTA_AMPLA = "de"

# A base começa em março de 1975, com a fusão da Guanabara.
ANOS = range(1975, 2027)

# "Legislações Gerais" NÃO se coleta. Medido: numa amostra de 1.000 resultados,
# 627 já estavam no acervo de leis ordinárias e a amostra de títulos veio com
# Resolução e Lei Ordinária misturadas — é view de apanhado, não espécie. Varrê-
# la seria recolher de novo o que já está aqui, e ela estoura o teto até por
# ano. Serve para outra coisa: conferir cobertura depois, contando quanto do que
# ela devolve o acervo já tem.
NAO_COLETAR = {"geral"}


def com_ponto(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def buscar_na_view(a: Alerj, view: str, consulta: str) -> list[tuple[str, str]]:
    """(unid, caminho) de cada documento devolvido pela busca naquela view."""
    resp = a._pedir(
        "POST",
        f"{BASE}/{view}?SearchView",
        data={"Query": consulta, "SearchOrder": "1", "SearchMax": "0"},
    )
    html = _decodifica_bytes(resp.content)
    # O href **não** termina em `?OpenDocument`: vem com `&amp;Highlight=0,de`
    # atrás, porque o Domino grifa o termo buscado. Exigir a aspa logo depois
    # devolvia zero — e zero aqui não parece erro, parece espécie vazia.
    achados = re.findall(
        r'href="(/contlei\.nsf/[0-9a-f]{32}/([0-9a-f]{32})\?OpenDocument[^"]*)"', html
    )
    vistos, saida = set(), []
    for caminho, unid in achados:
        if unid not in vistos:
            vistos.add(unid)
            saida.append((unid, caminho.split("&")[0]))
    return saida


def carregar_indice() -> dict[str, dict]:
    if not INDICE.exists():
        return {}
    return {
        json.loads(l)["unid"]: json.loads(l)
        for l in INDICE.read_text("utf-8").splitlines()
        if l.strip()
    }


def main() -> None:
    especies = json.loads(ESPECIES.read_text("utf-8"))
    indice = carregar_indice()
    progresso = json.loads(PROGRESSO.read_text("utf-8")) if PROGRESSO.exists() else {}
    a = Alerj(pausa=1.2)
    SAIDA.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(exist_ok=True)

    with INDICE.open("a", encoding="utf-8") as f:
        for especie, dados in especies.items():
            if especie == "lei_ordinaria" or not dados.get("view"):
                continue
            if especie in NAO_COLETAR:
                print(f"{especie}: view de apanhado, não se coleta (ver módulo)")
                continue
            if progresso.get(especie) == "completa":
                print(f"{especie}: já coletada")
                continue

            view = dados["view"]
            achados = buscar_na_view(a, view, CONSULTA_AMPLA)
            if len(achados) < TETO:
                print(f"{especie}: consulta ampla devolveu {len(achados)}")
            else:
                # Estourou o teto: a consulta ampla esconde o resto. Parte-se
                # por **ano**, não por número — medido na resolução: o ano mais
                # cheio devolve 664, bem abaixo do teto, e são 52 consultas em
                # vez das 4.800 que a varredura por número custaria.
                print(f"{especie}: ampla no teto ({len(achados)}); varrendo por ano")
                for ano in ANOS:
                    try:
                        achados.extend(buscar_na_view(a, view, str(ano)))
                    except Exception as exc:  # noqa: BLE001
                        print(f"   {ano}: {type(exc).__name__}", flush=True)
                    if ano % 10 == 0:
                        print(
                            f"   [{ano}] {len({u for u, _ in achados})} distintos",
                            flush=True,
                        )

            novos = 0
            for unid, caminho in achados:
                if unid in indice:
                    continue
                reg = {"unid": unid, "caminho": caminho, "especie_da_view": especie}
                indice[unid] = reg
                f.write(json.dumps(reg, ensure_ascii=False) + "\n")
                novos += 1
            f.flush()
            # Zero achados não é espécie vazia: é falha. Já aconteceu — uma
            # regex estrita demais devolveu zero nas cinco espécies, o passo se
            # marcou completo em zero segundo e a coleta seguiu como se
            # estivesse tudo em ordem. Espécie que não acha nada fica pendente,
            # para a próxima passada tentar de novo.
            if not achados:
                print(f"{especie}: NADA ACHADO — fica pendente")
                continue
            progresso[especie] = "completa"
            PROGRESSO.write_text(json.dumps(progresso, ensure_ascii=False), encoding="utf-8")
            print(f"{especie}: +{novos} atos novos no índice")

    pendentes = [
        r for r in indice.values() if not (DOCS / f"{r['unid']}.html").exists()
    ]
    print(f"\ndocumentos a baixar: {len(pendentes)} de {len(indice)}")
    t0 = time.monotonic()
    for i, reg in enumerate(pendentes, 1):
        try:
            html = a.documento("https://alerjln1.alerj.rj.gov.br" + reg["caminho"])
            (DOCS / f"{reg['unid']}.html").write_text(html, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"  {reg['unid'][:8]}: {type(exc).__name__}", flush=True)
            continue
        if i % 50 == 0:
            resta = (len(pendentes) - i) * (time.monotonic() - t0) / i / 60
            print(f"  [{i}/{len(pendentes)}] — faltam ~{resta:.0f} min", flush=True)
    print("espécies: fim")


if __name__ == "__main__":
    main()
