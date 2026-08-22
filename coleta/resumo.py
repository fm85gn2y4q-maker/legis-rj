"""Escreve o retrato do acervo a cada passada, para quem chegar amanhã.

Sem isto, saber como as coisas estão custa meia dúzia de contagens sobre
arquivos de gigabytes — e quem pergunta "e aí?" espera resposta, não uma
varredura. O orquestrador grava aqui os números que importam, e a conversa
seguinte lê um arquivo só.

Guarda também o retrato anterior: o que interessa numa coleta longa não é o
número, é se ele andou.
"""

from __future__ import annotations

import json
import pathlib
import time

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
DOERJ = DADOS / "doerj"
ARQUIVO = DADOS / "RESUMO.json"


def _linhas(caminho: pathlib.Path) -> int:
    if not caminho.exists():
        return 0
    return sum(1 for l in caminho.read_text("utf-8").splitlines() if l.strip())


def montar() -> dict:
    faltantes = DOERJ / "decretos_faltantes.json"
    tentados = DOERJ / "decretos_tentados.json"
    ausentes = json.loads(faltantes.read_text("utf-8")) if faltantes.exists() else []
    tentativas = json.loads(tentados.read_text("utf-8")) if tentados.exists() else {}
    achados = sum(1 for v in tentativas.values() if v.get("encontrado"))

    return {
        "em": time.strftime("%Y-%m-%d %H:%M:%S"),
        "alerj": {
            "documentos": sum(1 for _ in (DADOS / "alerj" / "docs").glob("*.html")),
            "concluida": (DADOS / "alerj" / "CONCLUIDA.json").exists(),
        },
        "doerj": {
            "edicoes": _linhas(DOERJ / "edicoes.jsonl"),
            "decretos_extraidos": _linhas(DOERJ / "decretos_todos.jsonl"),
            "recuperados": _linhas(DOERJ / "decretos_recuperados.jsonl"),
            "cadernos_abertos": sum(1 for _ in (DOERJ / "cadernos").glob("*.txt"))
            if (DOERJ / "cadernos").exists()
            else 0,
        },
        "recuperacao": {
            "ausentes_na_serie": len(ausentes),
            "tentados": len(tentativas),
            "encontrados": achados,
            "taxa": round(100 * achados / len(tentativas)) if tentativas else None,
            "de_brinde": sum(
                1 for v in tentativas.values() if v.get("encontrado") == "de brinde"
            ),
        },
        "banco": json.loads((DADOS / "alerj" / "banco_construido.json").read_text("utf-8"))
        if (DADOS / "alerj" / "banco_construido.json").exists()
        else None,
    }


def gravar() -> dict:
    atual = montar()
    if ARQUIVO.exists():
        try:
            atual["anterior"] = json.loads(ARQUIVO.read_text("utf-8"))
            atual["anterior"].pop("anterior", None)
        except json.JSONDecodeError:
            pass
    ARQUIVO.write_text(
        json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return atual


if __name__ == "__main__":
    print(json.dumps(gravar(), ensure_ascii=False, indent=2))
