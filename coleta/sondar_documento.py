"""Fase 1, parte 2 — o que o documento carrega.

A pergunta que decide o servidor inteiro: **de onde sai a vigência**. Num
acervo de legislação o erro que custa caro não é não achar a norma; é achar a
norma revogada e apresentá-la como fundamento. Então antes de modelar tabela:

  1. Que rótulos de metadado o ato traz (número, data, tipo, ementa, situação)?
  2. Revogação, nova redação e inconstitucionalidade aparecem como campo, ou
     como anotação solta no meio do texto?
  3. Com que frequência? Vale para o ato inteiro ou para o artigo?

Guarda o HTML cru em `dados/bruto/` — coletar e processar são fases separadas.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from alerj import Alerj  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
BRUTO = RAIZ / "dados" / "bruto"
SAIDA = RAIZ / "medicoes"

MARCAS = {
    "revogacao": r"[Rr]evogad[oa]",
    "revogacao_expressa_por": r"[Rr]evogad[oa]\s+pel[ao]",
    "nova_redacao": r"[Nn]ova\s+reda[çc][ãa]o",
    "inconstitucional": r"inconstitucional",
    "acao_direta": r"(?:ADI|A[çc][ãa]o\s+Direta|Representa[çc][ãa]o\s+de\s+Inconstitucionalidade|\bRI\s*\d)",
    "vide": r"\bVide\b",
    "vetado": r"[Vv]etad[oa]",
}


def cabecalho(sopa: BeautifulSoup) -> list[str]:
    """Primeiras linhas de texto do documento — é onde ficam os rótulos."""
    texto = sopa.get_text("\n", strip=True)
    linhas = [ln for ln in texto.split("\n") if ln.strip()]
    return linhas[:12]


def main() -> None:
    a = Alerj(pausa=1.5)
    BRUTO.mkdir(parents=True, exist_ok=True)
    SAIDA.mkdir(exist_ok=True)

    resultados = a.buscar(numero="443")
    print(f"busca numero=443 -> {len(resultados)} atos; amostrando 10")

    amostra = resultados[:: max(1, len(resultados) // 10)][:10]
    relatorio = []
    for i, r in enumerate(amostra, 1):
        html = a.documento(r)
        (BRUTO / f"{r.unid}.html").write_text(html, encoding="utf-8")
        sopa = BeautifulSoup(html, "html.parser")
        texto = sopa.get_text(" ", strip=True)
        contagem = {
            nome: len(re.findall(padrao, texto)) for nome, padrao in MARCAS.items()
        }
        item = {
            "unid": r.unid,
            "colunas_da_busca": r.colunas,
            "titulo": (sopa.title.get_text(strip=True) if sopa.title else ""),
            "cabecalho": cabecalho(sopa),
            "chars": len(texto),
            "marcas": contagem,
        }
        relatorio.append(item)
        print(
            f"[{i}] {r.unid[:8]}… {item['titulo'][:40]!r} "
            f"{item['chars']:>7} chars  {contagem}"
        )

    (SAIDA / "documentos.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\ncabeçalho do primeiro documento:")
    for linha in relatorio[0]["cabecalho"]:
        print("   ", linha[:120])


if __name__ == "__main__":
    main()
