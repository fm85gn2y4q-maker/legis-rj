"""Fase 1 do extrator — o que os documentos da ALERJ têm dentro.

Antes de escrever a primeira regex: **o que é um registro aqui?** A resposta
óbvia — um arquivo, um ato — esteve errada nos dois acervos anteriores, e no de
Mesquita um terço dos arquivos trazia mais de um ato.

Roda sobre o que já está em disco, sem tocar na rede. Mede:

  1. Que rótulos aparecem no cabeçalho, e em quantos documentos cada um.
  2. Quantas espécies distintas, e como o documento se identifica.
  3. Quantos trazem anotação de revogação, nova redação, inconstitucionalidade.
  4. Quantos NÃO casam com o formato esperado — que é onde mora o trabalho.
"""

from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DOCS = RAIZ / "dados" / "alerj" / "docs"

ROTULOS = re.compile(
    r"(Lei n[ºo°]|Lei Complementar n[ºo°]|Emenda n[ºo°]|Decreto n[ºo°]|"
    r"Resolu[çc][ãa]o n[ºo°]|Data da Lei|Data do Decreto|Data da Resolu[çc][ãa]o|"
    r"Data da Emenda|Texto da Lei|Texto do Decreto|Texto da Resolu[çc][ãa]o|"
    r"Texto da Emenda|Autoria|Ementa)",
    re.IGNORECASE,
)
SITUACAO = re.compile(r"\[\s*([^\]]{2,45}?)\s*\]")
MARCAS = {
    "revogado_por": r"[Rr]evogad[oa]\s+pel[ao]",
    "nova_redacao": r"[Nn]ova\s+reda[çc][ãa]o",
    "inconstitucional": r"inconstitucional",
    "orgao_especial": r"[ÓO]rg[ãa]o\s+Especial",
    "vetado": r"[Vv]etad[oa]",
}


def texto_de(html: str) -> str:
    sem_script = re.sub(r"(?s)<(script|style).*?</\1>", " ", html)
    return " ".join(re.sub(r"<[^>]+>", " ", sem_script).split())


def main() -> None:
    arquivos = sorted(DOCS.glob("*.html"))
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else len(arquivos)
    arquivos = arquivos[:limite]
    print(f"{len(arquivos)} documentos em disco")

    titulos = collections.Counter()
    rotulos = collections.Counter()
    situacoes = collections.Counter()
    marcas = collections.Counter()
    tamanhos = []
    sem_identidade = []

    for caminho in arquivos:
        html = caminho.read_text(encoding="utf-8", errors="replace")
        titulo = re.search(r"<title>(.*?)</title>", html, re.S)
        titulos[titulo.group(1).strip() if titulo else "(sem título)"] += 1

        texto = texto_de(html)
        tamanhos.append(len(texto))
        for r in set(m.group(0).title() for m in ROTULOS.finditer(texto[:600])):
            rotulos[r] += 1
        achado = SITUACAO.search(texto[:900])
        situacoes[achado.group(1) if achado else "(sem colchete)"] += 1
        for nome, padrao in MARCAS.items():
            if re.search(padrao, texto):
                marcas[nome] += 1
        # Identidade mínima: número e ano no começo do documento.
        if not re.search(r"n[ºo°]\s*[\d.]+\s*/?\s*\d{4}", texto[:400]):
            sem_identidade.append(caminho.name)

    print("\n--- espécie (título do documento) ---")
    for nome, n in titulos.most_common(12):
        print(f"{n:>6}  {nome[:60]}")

    print("\n--- rótulos no cabeçalho ---")
    for nome, n in rotulos.most_common(14):
        print(f"{n:>6}  {nome}")

    print("\n--- situação entre colchetes ---")
    for nome, n in situacoes.most_common(12):
        print(f"{n:>6}  {nome[:55]}")

    print("\n--- anotações no corpo ---")
    for nome, n in marcas.most_common():
        print(f"{n:>6}  {nome}  ({100 * n / len(arquivos):.0f}%)")

    tamanhos.sort()
    print(
        f"\ntexto: mediana {tamanhos[len(tamanhos) // 2]:,} chars, "
        f"maior {tamanhos[-1]:,}, menor {tamanhos[0]:,}"
    )
    print(f"sem número/ano no início: {len(sem_identidade)}")
    for nome in sem_identidade[:5]:
        print(f"    {nome}")

    (RAIZ / "medicoes").mkdir(exist_ok=True)
    (RAIZ / "medicoes" / "documentos_alerj.json").write_text(
        json.dumps(
            {
                "documentos": len(arquivos),
                "especies": titulos.most_common(),
                "rotulos": rotulos.most_common(),
                "situacoes": situacoes.most_common(),
                "marcas": marcas.most_common(),
                "sem_identidade": sem_identidade[:50],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
