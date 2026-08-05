"""Fase 1, parte 5 — a `decest.nsf` cobre mesmo a série de decretos?

É a pergunta que decide o que o acervo pode prometer. A sondagem anterior achou
o Decreto 49.792/2025 e **não** achou o 48.313/2023 — ou o formato do número
muda, ou há buraco na série. As duas respostas levam a projetos diferentes:
uma base com buraco não pode responder "não há decreto sobre X".

Método: amostra de números da série, cada um consultado em duas grafias (com e
sem ponto de milhar), conferindo se o número do documento devolvido é mesmo o
procurado — a busca é textual e traz também quem cita.

**A armadilha que a primeira versão desta sondagem caiu.** A consulta devolve
os N mais relevantes, não todos: procurar `5` marcou o Decreto-Lei nº 5/1975
como ausente, e ele existe — apareceu como primeira linha de outra busca. Um
número curto não sobe ao topo nem quando existe, e a sondagem estava provando
o que não pode provar. Por isso a amostra só usa **números de cinco dígitos**,
onde o token é raro o bastante para que a ausência signifique alguma coisa.
Ausência aqui continua sendo indício, não prova.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from sondar_decest import buscar  # noqa: E402

import requests  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent

# Só cinco dígitos — ver a armadilha no topo do módulo. Cobrem de 1997
# (10.000) ao decreto mais recente do Estado (perto do 49.800), passando de
# cem em cem na faixa onde a série termina.
AMOSTRA = [
    10_000, 15_000, 20_000, 25_000, 30_000, 35_000, 40_000, 41_528,
    42_000, 42_100, 42_200, 42_300, 42_500, 42_800,
    43_000, 44_000, 45_000, 46_000, 47_000, 48_000, 48_313, 49_000, 49_792,
]


def com_ponto(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def numero_da_linha(colunas: list[str]) -> str:
    """A 1ª coluna da view é o número do ato."""
    return colunas[0] if colunas else ""


def main() -> None:
    sessao = requests.Session()
    sessao.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

    relatorio = {}
    for n in AMOSTRA:
        achou = {}
        for grafia in (com_ponto(n), str(n)):
            linhas = buscar(sessao, f'"{grafia}"', maximo="50")
            exatos = [
                lin
                for lin in linhas
                if numero_da_linha(lin["colunas"]).replace(".", "").lstrip("0")
                == str(n)
            ]
            achou[grafia] = {"resultados": len(linhas), "exatos": len(exatos)}
            if exatos:
                achou[grafia]["primeiro"] = exatos[0]["colunas"][:3]
        relatorio[n] = achou
        marca = "ok " if any(v["exatos"] for v in achou.values()) else "AUSENTE"
        print(f"  {marca} decreto {com_ponto(n):>7} -> {achou}")

    destino = RAIZ / "medicoes" / "decest_cobertura.json"
    destino.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ausentes = [n for n, v in relatorio.items() if not any(x["exatos"] for x in v.values())]
    print(f"\nausentes na amostra: {len(ausentes)}/{len(AMOSTRA)} -> {ausentes}")
    print(f"gravado em {destino}")


if __name__ == "__main__":
    main()
