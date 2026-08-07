"""Roda o extrator sobre tudo o que está em disco e diz onde ele falha.

Não é teste: é medição. O que interessa não é "passou", é **quantos ficaram
sem cada campo, e quais**. Campo faltando em 3% dos documentos é uma coisa;
em 39%, é um defeito estrutural — foi exatamente esse o número antes de tratar
o grifo da busca.

Confere também a coerência entre o cabeçalho e a linha de abertura do ato: os
dois trazem número e data, e discordarem é sinal de extração errada num dos
dois lados, não de erro da fonte.
"""

from __future__ import annotations

import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from extrair import extrair  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DOCS = RAIZ / "dados" / "alerj" / "docs"


def main() -> None:
    arquivos = sorted(DOCS.glob("*.html"))
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else len(arquivos)
    arquivos = arquivos[:limite]
    print(f"{len(arquivos)} documentos")

    faltando = collections.Counter()
    situacoes = collections.Counter()
    anotados = collections.Counter()
    divergentes = []
    exemplos_sem_numero = []

    for caminho in arquivos:
        reg = extrair(
            caminho.read_text(encoding="utf-8", errors="replace"), caminho.stem
        )
        for campo in ("numero", "ano", "data", "situacao"):
            if not reg.get(campo):
                faltando[campo] += 1
                if campo == "numero" and len(exemplos_sem_numero) < 5:
                    exemplos_sem_numero.append((caminho.name, reg["texto"][:150]))
        situacoes[reg.get("situacao", "(sem)")] += 1
        for nome in reg.get("anotacoes", {}):
            anotados[nome] += 1

        abertura = reg.get("abertura")
        if not abertura:
            faltando["abertura"] += 1
        elif abertura.get("data") and reg.get("data") and abertura["data"] != reg["data"]:
            # Cabeçalho e abertura discordando na DATA é o que interessa
            # conferir: um vem do campo em MM/DD/AAAA, o outro da data por
            # extenso. Discordarem denuncia leitura errada do formato.
            divergentes.append((caminho.stem[:10], reg["data"], abertura["data"]))

    total = len(arquivos)
    print("\n--- campos faltando ---")
    for campo in ("numero", "ano", "data", "situacao"):
        n = faltando[campo]
        print(f"{n:>6}  {campo}  ({100 * n / total:.1f}%)")

    print("\n--- situação ---")
    for nome, n in situacoes.most_common(10):
        print(f"{n:>6}  {nome[:50]}")

    print("\n--- documentos com anotação ---")
    for nome, n in anotados.most_common():
        print(f"{n:>6}  {nome}  ({100 * n / total:.1f}%)")

    print(
        f"\n--- a fonte discorda de si mesma na data: {len(divergentes)} "
        f"({100 * len(divergentes) / total:.1f}%) ---"
    )
    for unid, cab, ab in divergentes[:8]:
        print(f"    {unid}  campo {cab}  texto {ab}")

    if exemplos_sem_numero:
        print("\n--- sem número (amostra) ---")
        for nome, trecho in exemplos_sem_numero:
            print(f"    {nome[:12]}: {trecho[:110]}")

    (RAIZ / "medicoes").mkdir(exist_ok=True)
    (RAIZ / "medicoes" / "extrator.json").write_text(
        json.dumps(
            {
                "documentos": total,
                "faltando": dict(faltando),
                "situacoes": situacoes.most_common(),
                "anotacoes": anotados.most_common(),
                "divergentes": len(divergentes),
                "exemplos_divergentes": divergentes[:30],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
