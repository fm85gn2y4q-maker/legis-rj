"""Fase 1, parte 8 — a republicação no DOERJ, e o quanto ela ameaça o acervo.

O risco nº 1 do acervo de diários de Mesquita: o ente publica o ato, percebe o
erro e republica dias depois. A busca textual devolve a versão errada e a
corrigida com a mesma confiança, e nada no texto da primeira avisa que ela foi
refeita. Antes de varrer dezesseis anos de DOERJ é preciso saber se aqui é a
mesma história — e com que frequência.

Método: amostra de edições espalhadas pelos anos, texto extraído do PDF, e
contagem das marcas. Interessa especialmente a marca **perto de decreto**: uma
errata de extrato de contrato não me atrapalha; uma republicação de decreto,
sim.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from ioerj import Edicao, Ioerj  # noqa: E402
from ferramentas import PDFTOTEXT  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
BRUTO = RAIZ / "dados" / "bruto" / "doerj"

MARCAS = {
    "republicacao": r"[Rr]epublicad[oa]|REPUBLICA[ÇC][ÃA]O|REPUBLICAD[OA]",
    "errata": r"[Ee]rrata|ERRATA",
    "retificacao": r"[Rr]etifica[çc][ãa]o|RETIFICA[ÇC][ÃA]O",
    "incorrecao": r"incorre[çc][ãa]o",
}
# "DECRETO Nº 48.313 … (republicado)" — a marca a menos de 400 caracteres da
# palavra DECRETO. Distância arbitrária, escolhida por caber num ato curto.
PERTO_DE_DECRETO = re.compile(
    r"DECRETO[^\n]{0,400}?(?:[Rr]epublicad|REPUBLICAD|[Ee]rrata|ERRATA|"
    r"[Rr]etifica|RETIFICA)",
    re.DOTALL,
)


def texto_do_pdf(pdf: pathlib.Path) -> str:
    saida = pdf.with_suffix(".txt")
    if not saida.exists():
        subprocess.run(
            [PDFTOTEXT, "-enc", "UTF-8", str(pdf), str(saida)],
            check=True, capture_output=True, timeout=600,
        )
    return saida.read_text(encoding="utf-8", errors="replace")


def main() -> None:
    indice = json.loads((RAIZ / "dados" / "calendario.json").read_text("utf-8"))
    io = Ioerj()
    BRUTO.mkdir(parents=True, exist_ok=True)

    # Uma edição por ano, sempre a mesma posição relativa, para não escolher
    # a dedo o que confirma a hipótese.
    por_ano: dict[str, dict] = {}
    for item in indice:
        por_ano.setdefault(item["data"][:4], item)
    amostra = [por_ano[a] for a in sorted(por_ano) if a >= "2010"]

    relatorio = []
    for item in amostra:
        destino = BRUTO / f"{item['data']}.pdf"
        if not destino.exists():
            destino.write_bytes(io.pdf_por_sessao(item["sessao"]))
        texto = texto_do_pdf(destino)
        contagem = {
            nome: len(re.findall(padrao, texto)) for nome, padrao in MARCAS.items()
        }
        perto = len(PERTO_DE_DECRETO.findall(texto))
        paginas = texto.count("\f") or 1
        relatorio.append(
            {
                "data": item["data"],
                "mb": round(destino.stat().st_size / 1e6, 1),
                "paginas": paginas,
                "chars_por_pagina": round(len(texto) / paginas),
                "marcas": contagem,
                "marca_perto_de_decreto": perto,
            }
        )
        print(
            f"{item['data']}  {relatorio[-1]['mb']:>5} MB  {paginas:>3} pág  "
            f"{relatorio[-1]['chars_por_pagina']:>6} c/pág  "
            f"{contagem}  perto de decreto: {perto}"
        )

    total = sum(sum(r["marcas"].values()) for r in relatorio)
    perto = sum(r["marca_perto_de_decreto"] for r in relatorio)
    print(f"\n{len(relatorio)} edições | {total} marcas | {perto} perto de decreto")

    (RAIZ / "medicoes" / "republicacao.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
