"""Descobre a data de publicação dos decretos ausentes — pelas citações.

O acervo não tem a publicação original destes 224 decretos, mas tem milhares
de atos que os citam, e a citação administrativa traz a data por extenso:

    "em conformidade com o Art. 1º, do Decreto nº 44.251, de 17 de junho de 2013"

Com a data dá para procurar o caderno daquele dia. Sem ela, não há por onde
começar: o número sozinho não diz em que edição procurar.

Quando as citações discordarem da data, fica a mais frequente — erro de
digitação em citação isolada não deve mandar na busca.
"""

from __future__ import annotations

import collections
import json
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DOERJ = RAIZ / "dados" / "doerj"

MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}

# "Decreto nº 44.251, de 17 de junho de 2013" e "Decreto nº 48.244 de 04/11/2022"
POR_EXTENSO = re.compile(
    r"[Dd]ecreto\s+(?:[Ee]stadual\s+)?n?[ºo°.]{0,2}\s*(\d{2}\.?\d{3})[,\s]+de\s+"
    r"(\d{1,2})[ºo°]?\s+de\s+([A-Za-zçÇãÃéÉ]+)\s+de\s+(\d{4})",
)
NUMERICA = re.compile(
    r"[Dd]ecreto\s+(?:[Ee]stadual\s+)?n?[ºo°.]{0,2}\s*(\d{2}\.?\d{3})[,\s]+de\s+"
    r"(\d{1,2})/(\d{1,2})/(\d{4})",
)


def main() -> None:
    ausentes = set(json.loads((DOERJ / "decretos_sem_materia.json").read_text("utf-8")))
    datas: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)

    arquivos = sorted(DOERJ.glob("*.txt"))
    print(f"lendo {len(arquivos)} edições…")
    for i, caminho in enumerate(arquivos, 1):
        texto = caminho.read_text(encoding="utf-8", errors="replace")
        for achado in POR_EXTENSO.finditer(texto):
            numero = int(achado.group(1).replace(".", ""))
            if numero not in ausentes:
                continue
            mes = MESES.get(achado.group(3).lower())
            if mes:
                datas[numero][
                    f"{int(achado.group(4)):04d}-{mes:02d}-{int(achado.group(2)):02d}"
                ] += 1
        for achado in NUMERICA.finditer(texto):
            numero = int(achado.group(1).replace(".", ""))
            if numero not in ausentes:
                continue
            datas[numero][
                f"{int(achado.group(4)):04d}-{int(achado.group(3)):02d}-"
                f"{int(achado.group(2)):02d}"
            ] += 1
        if i % 1000 == 0:
            print(f"  {i}/{len(arquivos)} — {len(datas)} com data", flush=True)

    resultado = {}
    discordantes = 0
    for numero, contagem in datas.items():
        escolhida, vezes = contagem.most_common(1)[0]
        if len(contagem) > 1:
            discordantes += 1
        resultado[str(numero)] = {
            "data": escolhida,
            "citacoes": vezes,
            "outras_datas": [d for d in contagem if d != escolhida][:3],
        }

    print(f"\ncom data descoberta: {len(resultado)} de {len(ausentes)}")
    print(f"citações que discordam entre si: {discordantes}")
    (DOERJ / "datas_dos_ausentes.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"gravado em {DOERJ / 'datas_dos_ausentes.json'}")


if __name__ == "__main__":
    main()
