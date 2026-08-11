"""A conferência de série: que atos deviam existir e não estão no acervo.

É a prova de completude do acervo, e ela não depende da varredura ter sido
exaustiva. A numeração de cada espécie é sequencial: sabendo o maior número
alcançado, sabe-se exatamente quais faltam. Buraco na sequência é ato que a
busca não devolveu — e cada um vira uma consulta dirigida, que é barata.

O que o resultado NÃO significa: buraco aqui não prova que o ato existe. A
numeração pula de verdade — ato vetado e não promulgado, número reservado e
não usado, projeto que virou outra coisa. Prova só que **nós** não o temos, e
que vale perguntar à fonte por ele, um a um.

Cruza também com as consultas que estouraram o teto de 1.000 durante a coleta:
se os buracos se concentrarem nos números dessas consultas, a causa é o teto —
e não a fonte.
"""

from __future__ import annotations

import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from extrair import extrair  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DOCS = RAIZ / "dados" / "alerj" / "docs"
ALERJ = RAIZ / "dados" / "alerj"


def especie_por_unid() -> dict[str, str]:
    """A view de onde o ato veio é a melhor pista de espécie antes de ler."""
    mapa = {}
    indice = ALERJ / "indice.jsonl"
    if indice.exists():
        for linha in indice.read_text("utf-8").splitlines():
            if linha.strip():
                mapa[json.loads(linha)["unid"]] = "lei_ordinaria"
    outras = ALERJ / "indice_especies.jsonl"
    if outras.exists():
        for linha in outras.read_text("utf-8").splitlines():
            if linha.strip():
                reg = json.loads(linha)
                mapa[reg["unid"]] = reg["especie_da_view"]
    return mapa


def main() -> None:
    origem = especie_por_unid()
    arquivos = sorted(DOCS.glob("*.html"))
    print(f"lendo {len(arquivos)} documentos…")

    por_especie: dict[str, dict[int, list[str]]] = collections.defaultdict(dict)
    titulos = collections.Counter()
    sem_numero = 0
    com_sufixo = []

    for i, caminho in enumerate(arquivos, 1):
        reg = extrair(
            caminho.read_text(encoding="utf-8", errors="replace"), caminho.stem
        )
        especie = origem.get(caminho.stem, "desconhecida")
        titulos[(especie, reg.get("especie", ""))] += 1
        numero = reg.get("numero")
        if not numero:
            sem_numero += 1
            continue
        if not numero.isdigit():
            com_sufixo.append((especie, numero, reg.get("ano")))
            continue
        por_especie[especie].setdefault(int(numero), []).append(reg.get("ano", ""))
        if i % 2000 == 0:
            print(f"  {i}/{len(arquivos)}", flush=True)

    print("\n--- espécie da view × título do documento ---")
    for (view, titulo), n in titulos.most_common(12):
        marca = "" if view.replace("_", " ") in titulo.lower() else "   <-- confere"
        print(f"{n:>6}  view={view:<22} título={titulo[:28]}{marca}")

    print(f"\nsem número: {sem_numero} | com sufixo de letra: {len(com_sufixo)}")

    relatorio = {}
    print("\n--- buracos na numeração ---")
    for especie, numeros in sorted(por_especie.items()):
        if not numeros:
            continue
        maior = max(numeros)
        faltando = [n for n in range(1, maior + 1) if n not in numeros]
        duplicados = {n: anos for n, anos in numeros.items() if len(anos) > 1}
        relatorio[especie] = {
            "atos": len(numeros),
            "maior_numero": maior,
            "faltando": faltando,
            "quantos_faltam": len(faltando),
            "numeros_repetidos": len(duplicados),
        }
        print(
            f"{especie:<24} {len(numeros):>6} atos | maior {maior:>6} | "
            f"faltam {len(faltando):>5} | repetidos {len(duplicados):>4}"
        )

    progresso = json.loads((ALERJ / "progresso.json").read_text("utf-8"))
    truncadas = set(progresso.get("truncadas", []))
    if truncadas and "lei_ordinaria" in relatorio:
        faltando = set(relatorio["lei_ordinaria"]["faltando"])
        print(
            f"\nconsultas truncadas: {len(truncadas)} | "
            f"delas ausentes do acervo: {len(truncadas & faltando)}"
        )

    (RAIZ / "medicoes").mkdir(exist_ok=True)
    (RAIZ / "medicoes" / "serie.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\ngravado em {RAIZ / 'medicoes' / 'serie.json'}")


if __name__ == "__main__":
    main()
