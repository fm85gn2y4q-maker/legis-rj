"""Prova o acervo contra casos que já sabemos como devem sair.

Não é teste de unidade: é conferência contra a realidade. Cada caso aqui foi
encontrado à mão durante a construção, e o que se verifica é se o acervo
responde sobre ele o que a fonte declara — inclusive quando o que a fonte
declara é "nada".
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from legis_rj.acervo import Acervo, interpretar_referencia

BANCO = Path(__file__).resolve().parent / "banco" / "legis-rj.sqlite"


def main() -> None:
    a = Acervo(BANCO)

    print("=== 1. cobertura ===")
    c = a.cobertura()
    print(f"total: {c['total']} atos")
    for especie, dados in c["por_especie"].items():
        print(
            f"  {dados['atos']:>6}  {dados['rotulo']:<24} {dados['anos']}  "
            f"vigência: {'sim' if dados['vigencia_disponivel'] else 'NÃO EXISTE NA FONTE'}"
        )
    print(f"divergências da fonte: {c['divergencias_da_fonte']}")

    print("\n=== 2. referência escrita como numa peça ===")
    for texto in ("lei 5427/2009", "LC 232", "EC nº 99", "lei complementar 210"):
        print(f"  {texto!r} -> {interpretar_referencia(texto)}")

    print("\n=== 3. a lei do processo administrativo ===")
    achados = a.obter("lei_ordinaria", "5427", "2009")
    for ato in achados:
        print(f"  {ato.citacao}")
        print(f"  situação: {ato.situacao} (origem: {ato.situacao_origem})")
        print(f"  ementa: {(ato.ementa or '')[:90]}")

    print("\n=== 4. vigência em dois níveis: Lei 4.024/2002 ===")
    for ato in a.obter("lei_ordinaria", "4024", "2002"):
        v = a.vigencia(ato)
        print(f"  {v['citacao']}")
        print(f"  ato: {v['declarado']['ato']}")
        for tipo, trechos in v["declarado"]["dispositivos"].items():
            print(f"  dispositivo/{tipo}: {len(trechos)} anotação(ões)")
            for t in trechos[:2]:
                print(f"     - {t[:100]}")
        for aviso in v["avisos"]:
            print(f"  aviso: {aviso[:100]}")

    print("\n=== 5. espécie sem vigência declarada na fonte ===")
    linha = a.con.execute(
        "SELECT numero, ano FROM ato WHERE especie='decreto_legislativo' "
        "AND numero IS NOT NULL LIMIT 1"
    ).fetchone()
    if linha:
        for ato in a.obter("decreto_legislativo", linha["numero"], linha["ano"]):
            v = a.vigencia(ato)
            print(f"  {v['citacao']}: situação={v['declarado']['ato']}")
            print(f"  aviso: {v['avisos'][0][:110]}")

    print("\n=== 6. busca por ementa × inteiro teor ===")
    ementa = a.pesquisar_ementa("saneamento básico", limite=3)
    print(f"  ementa: {len(ementa)} achados")
    for ato in ementa:
        print(f"     {ato.citacao} — {(ato.ementa or '')[:70]}")
    teor = a.pesquisar_texto("saneamento básico", limite=3)
    print(f"  inteiro teor: {len(teor)} achados")
    for x in teor:
        print(f"     {x['ato'].citacao} — {x['trecho'][:80]}")

    print("\n=== 7. o ato com número divergente ===")
    linha = a.con.execute(
        "SELECT unid FROM ato WHERE numero_divergente IS NOT NULL LIMIT 1"
    ).fetchone()
    if linha:
        ato = a._ato(
            a.con.execute("SELECT * FROM ato WHERE unid=?", (linha["unid"],)).fetchone()
        )
        print(f"  {ato.citacao}")
        for aviso in ato.avisos:
            print(f"  aviso: {aviso}")

    print("\n=== 8. revogados ===")
    for ato in a.pesquisar_ementa("imposto", situacao="Revogado", limite=3):
        print(f"  {ato.citacao} — {ato.situacao} ({ato.situacao_origem})")


if __name__ == "__main__":
    main()
