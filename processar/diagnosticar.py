"""Lê todos os documentos uma vez e grava o extraído — para não reler a cada dúvida.

Ler 12.700 arquivos leva dez minutos. Fazer isso a cada pergunta ("quais números
estão fora da faixa?", "quais se repetem?") desperdiça a tarde. Aqui a leitura é
uma só: o resultado vai para `dados/alerj/extraido.jsonl`, e toda conferência
passa a ser sobre esse arquivo.

Grava sem o texto integral — ele é grande e já está no HTML de origem. O que
fica é o que identifica e qualifica o ato.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from extrair import extrair  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ALERJ = RAIZ / "dados" / "alerj"
DOCS = ALERJ / "docs"
SAIDA = ALERJ / "extraido.jsonl"


def origem_por_unid() -> dict[str, str]:
    mapa = {}
    for arquivo, rotulo in (
        (ALERJ / "indice.jsonl", "lei_ordinaria"),
        (ALERJ / "indice_especies.jsonl", None),
    ):
        if not arquivo.exists():
            continue
        for linha in arquivo.read_text("utf-8").splitlines():
            if linha.strip():
                reg = json.loads(linha)
                mapa[reg["unid"]] = rotulo or reg["especie_da_view"]
    return mapa


def main() -> None:
    origem = origem_por_unid()
    arquivos = sorted(DOCS.glob("*.html"))
    print(f"{len(arquivos)} documentos")
    with SAIDA.open("w", encoding="utf-8") as f:
        for i, caminho in enumerate(arquivos, 1):
            reg = extrair(
                caminho.read_text(encoding="utf-8", errors="replace"), caminho.stem
            )
            reg.pop("texto", None)
            reg["especie_da_view"] = origem.get(caminho.stem, "desconhecida")
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
            if i % 2000 == 0:
                print(f"  {i}/{len(arquivos)}", flush=True)
    print(f"gravado em {SAIDA}")


if __name__ == "__main__":
    main()
