"""Fase 1, parte 7 — quanto custa varrer dezesseis anos de Diário Oficial.

A parte 6 mostrou que o caminho existe e que o PDF tem texto nativo. Falta o
que decide se a varredura é viável:

  1. **Teto da busca.** Uma consulta trouxe exatamente 100 resultados — número
     redondo demais para ser coincidência. Se 100 é teto, o dia com mais de 100
     matérias perde o excedente sem avisar.
  2. **Quantos decretos por dia**, para dimensionar o acervo e saber se o teto
     ameaça a varredura diária.
  3. **A rota do calendário.** Se der para abrir a edição de uma data direto,
     a varredura dispensa a busca — e passa a não depender do que o índice de
     texto do site indexou.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from ioerj import BASE, Ioerj, _absoluto, _decodifica  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent

DIAS = [("10", "01", "2023"), ("15", "03", "2016"), ("07", "05", "2010")]


def main() -> None:
    io = Ioerj()
    medicoes: dict[str, object] = {}

    print("[1] teto da busca")
    tetos = {}
    for termo in ["decreto", "estado", "secretaria"]:
        materias, _ = io.buscar(termo)
        tetos[termo] = len(materias)
        print(f"    {termo!r} sem data -> {len(materias)} matérias")
    medicoes["teto"] = tetos

    print("\n[2] decretos por dia")
    por_dia = {}
    for dia, mes, ano in DIAS:
        materias, _ = io.buscar("decreto", dia=dia, mes=mes, ano=ano)
        normativos = [m for m in materias if "Decreto Normativo" in m.tipo]
        pessoais = [m for m in materias if "Decreto Pessoal" in m.tipo]
        por_dia[f"{dia}/{mes}/{ano}"] = {
            "materias": len(materias),
            "decreto_normativo": len(normativos),
            "decreto_pessoal": len(pessoais),
            "paginas_distintas": sorted({m.pagina for m in normativos}),
        }
        print(
            f"    {dia}/{mes}/{ano}: {len(materias)} matérias | "
            f"{len(normativos)} decreto normativo | {len(pessoais)} pessoal"
        )
    medicoes["por_dia"] = por_dia

    print("\n[3] rota do calendário")
    materias, _ = io.buscar("decreto", dia="10", mes="01", ano="2023")
    r1 = io.s.get(_absoluto(materias[0].href_publicacao), timeout=120)
    m = re.search(r"(/portal/[^\s\"'>]*mostra_edicao[^\s\"'>]*)", _decodifica(r1.content))
    visualizador = _absoluto(m.group(1).replace("&amp;", "&"))
    r2 = io.s.get(visualizador, timeout=120)
    html = _decodifica(r2.content)
    calendario = re.search(r"(/portal/[^\s\"'>]*calendario=true[^\s\"'>]*)", html)
    medicoes["calendario"] = {"link": bool(calendario)}
    if calendario:
        url = _absoluto(calendario.group(1).replace("&amp;", "&"))
        r3 = io.s.get(url, timeout=120)
        pagina = _decodifica(r3.content)
        sessoes = re.findall(r"session=([A-Za-z0-9+/=]{20,})", pagina)
        datas = re.findall(r"(\d{2}/\d{2}/\d{4})", pagina)
        medicoes["calendario"].update(
            {
                "status": r3.status_code,
                "chars": len(pagina),
                "sessoes_oferecidas": len(set(sessoes)),
                "datas_visiveis": sorted(set(datas))[:8],
            }
        )
        print(
            f"    calendário: {r3.status_code}, {len(pagina)} chars, "
            f"{len(set(sessoes))} sessões, datas {sorted(set(datas))[:5]}"
        )
    else:
        print("    não achei link de calendário")

    destino = RAIZ / "medicoes" / "doerj_varredura.json"
    destino.write_text(json.dumps(medicoes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ngravado em {destino}")


if __name__ == "__main__":
    main()
