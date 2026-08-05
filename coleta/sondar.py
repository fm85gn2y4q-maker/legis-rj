"""Fase 1 — medir o pressuposto antes de escrever o coletor.

Não coleta nada: só responde, contra o servidor real, as perguntas de que a
coleta depende. O resultado vai para `medicoes/sondagem.json`.

Perguntas:
  1. O que a página de resultado devolve por linha? (colunas, situação)
  2. A busca por número de lei funciona? Em que formato?
  3. `MaxResults=0` devolve mesmo tudo, ou o servidor corta? Qual é o teto?
  4. A busca alcança as outras espécies (lei complementar, emenda, decreto
     legislativo, resolução) ou só lei ordinária?
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from alerj import Alerj  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "medicoes"


def main() -> None:
    a = Alerj(pausa=2.0)
    medicoes: dict[str, object] = {}

    print("[1] estrutura da linha de resultado")
    r = a.buscar(texto="saneamento")
    medicoes["estrutura"] = {
        "total": len(r),
        "amostra": [{"unid": x.unid, "colunas": x.colunas} for x in r[:4]],
    }
    print(f"    {len(r)} resultados; colunas da 1ª: {r[0].colunas if r else '—'}")

    print("[2] busca por número")
    numeros = {}
    for forma in ["443", "11293", "11.293", "0443"]:
        try:
            n = len(a.buscar(numero=forma))
        except Exception as exc:  # noqa: BLE001
            n = f"erro: {exc}"
        numeros[forma] = n
        print(f"    ProposicaoBusca={forma!r} -> {n}")
    medicoes["busca_por_numero"] = numeros

    print("[3] teto de resultados")
    tetos = {}
    for termo in ["dispõe", "estado", "lei"]:
        try:
            n = len(a.buscar(texto=termo))
        except Exception as exc:  # noqa: BLE001
            n = f"erro: {exc}"
        tetos[termo] = n
        print(f"    Busca={termo!r} MaxResults=0 -> {n}")
    medicoes["teto"] = tetos

    print("[4] espécies alcançadas pela busca")
    especies = {}
    for termo in [
        "lei complementar",
        "emenda constitucional",
        "decreto legislativo",
        "resolução",
    ]:
        try:
            n = len(a.buscar(texto=f'"{termo}"'))
        except Exception as exc:  # noqa: BLE001
            n = f"erro: {exc}"
        especies[termo] = n
        print(f"    {termo!r} -> {n}")
    medicoes["especies"] = especies

    SAIDA.mkdir(exist_ok=True)
    destino = SAIDA / "sondagem.json"
    destino.write_text(
        json.dumps(medicoes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\ngravado em {destino}")


if __name__ == "__main__":
    main()
