"""Espera a busca dirigida dos decretos fechar, e sai quando fechar.

Duas condições, e as duas precisam valer:

  1. todos os números da lista de faltantes foram procurados;
  2. toda edição localizada já foi baixada e extraída.

Parar na primeira anunciaria fim com os downloads por fazer — que é a parte
cara. Já aconteceu com a ALERJ: a fase A terminou e a B mal tinha começado.

Grava `dados/doerj/DECRETOS_CONCLUIDO.json` ao terminar, porque o aviso não
pode depender de haver alguém olhando: isto anda pela Tarefa Agendada, de
madrugada, sem conversa aberta.
"""

from __future__ import annotations

import json
import pathlib
import time

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DOERJ = RAIZ / "dados" / "doerj"
INTERVALO = 180


def estado() -> tuple[int, int, int, int]:
    numeros = json.loads((DOERJ / "decretos_faltantes.json").read_text("utf-8"))
    localizados = []
    caminho = DOERJ / "decretos_localizados.jsonl"
    if caminho.exists():
        localizados = [
            json.loads(l) for l in caminho.read_text("utf-8").splitlines() if l.strip()
        ]
    edicoes = {
        m["data"] for r in localizados for m in r.get("materias", []) if m.get("data")
    }
    extraidas = set()
    saida = DOERJ / "decretos_extras.jsonl"
    if saida.exists():
        extraidas = {
            json.loads(l)["data_publicacao"]
            for l in saida.read_text("utf-8").splitlines()
            if l.strip()
        }
    return len(numeros), len(localizados), len(edicoes), len(extraidas)


def main() -> None:
    while True:
        alvo, localizados, edicoes, extraidas = estado()
        pronto = localizados >= alvo and edicoes and extraidas >= edicoes * 0.95
        if pronto:
            resumo = {
                "concluido_em": time.strftime("%Y-%m-%d %H:%M:%S"),
                "numeros_procurados": localizados,
                "edicoes_localizadas": edicoes,
                "edicoes_extraidas": extraidas,
            }
            (DOERJ / "DECRETOS_CONCLUIDO.json").write_text(
                json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"DECRETOS CONCLUÍDO — {resumo}", flush=True)
            return
        print(
            f"{time.strftime('%H:%M')}  localizados {localizados}/{alvo} · "
            f"edições {extraidas}/{edicoes}",
            flush=True,
        )
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
