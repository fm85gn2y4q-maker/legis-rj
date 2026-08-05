"""Baixa o calendário do DOERJ e confere se ele tem buraco.

Duas funções numa só: é a medida que faltava — *o calendário cobre 2010 sem
falha?* — e é o índice de que a coleta vai viver, porque cada edição entra por
ele. Grava `dados/calendario.json`.

A conferência não é contar edições: é comparar com os **dias úteis** de cada
ano. Diário oficial não sai em sábado, domingo nem feriado, e a média mensal
esconde exatamente o que interessa — um mês com 20 edições pode ter pulado três
dias úteis e ganho três sábados de suplemento.

Feriado nacional entra pela lista abaixo; feriado estadual e ponto facultativo,
não. Por isso um punhado de dias úteis sem edição é normal, e o que se procura
é **rombo**: semana inteira faltando, mês inteiro faltando.
"""

from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter
from datetime import date, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from ioerj import Ioerj  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "dados" / "calendario.json"

# Feriados nacionais fixos. Os móveis (Carnaval, Sexta-feira Santa, Corpus
# Christi) ficam de fora de propósito: entram como "dia útil sem edição", e é
# melhor um falso alarme do que uma tabela de datas móveis errada.
FERIADOS_FIXOS = {(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (12, 25)}


def dias_uteis(ano: int) -> list[date]:
    d, fim, saida = date(ano, 1, 1), date(ano, 12, 31), []
    while d <= fim:
        if d.weekday() < 5 and (d.month, d.day) not in FERIADOS_FIXOS:
            saida.append(d)
        d += timedelta(days=1)
    return saida


def main() -> None:
    io = Ioerj()
    print("baixando o calendário…")
    edicoes = io.calendario()
    print(f"{len(edicoes)} edições, de {edicoes[-1].data} a {edicoes[0].data}")

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        json.dumps(
            [{"data": e.data, "sessao": e.sessao, "uuid": e.uuid} for e in edicoes],
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )

    datas = {e.data for e in edicoes}
    if len(datas) != len(edicoes):
        print(f"atenção: {len(edicoes) - len(datas)} datas repetidas no calendário")

    por_ano = Counter(e.data[:4] for e in edicoes)
    hoje = date.today()
    print("\nano  edições  dias úteis  faltando  maior rombo")
    relatorio = {}
    for ano in sorted(por_ano):
        uteis = [d for d in dias_uteis(int(ano)) if d <= hoje]
        ausentes = [d for d in uteis if d.isoformat() not in datas]
        rombo = _maior_sequencia(ausentes)
        relatorio[ano] = {
            "edicoes": por_ano[ano],
            "dias_uteis": len(uteis),
            "faltando": len(ausentes),
            "maior_rombo": rombo,
        }
        marca = "  <-- olhar" if rombo >= 5 else ""
        print(
            f"{ano}  {por_ano[ano]:>7}  {len(uteis):>10}  {len(ausentes):>8}  "
            f"{rombo:>11}{marca}"
        )

    (RAIZ / "medicoes" / "calendario.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\níndice em {DESTINO}")


def _maior_sequencia(faltando: list[date]) -> int:
    maior = atual = 0
    anterior = None
    for d in faltando:
        atual = atual + 1 if anterior and (d - anterior).days <= 3 else 1
        maior = max(maior, atual)
        anterior = d
    return maior


if __name__ == "__main__":
    main()
