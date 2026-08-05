"""Fase 1, parte 6 — dá para tirar do DOERJ os decretos que a ALERJ não tem?

A base da ALERJ para no Decreto 42.200, de 22/12/2009. Faltam dezesseis anos.
O Diário Oficial é a fonte autoritativa do que foi publicado — a pergunta é se
ele é **coletável**, e isso se decide em quatro medidas:

  1. A busca sem data funciona, ou obriga a varrer dia a dia?
  2. Quantos resultados ela devolve de fato? (o site anuncia um total e lista
     outro — o que vale é o que ela lista)
  3. O decreto se acha pelo número? Em que grafia?
  4. O PDF da edição tem texto nativo, ou é imagem? Qual o peso por edição?

A quarta decide o custo do acervo inteiro: página de imagem exige OCR, e OCR
sobre dezesseis anos de Diário Oficial é outro projeto.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from ioerj import Ioerj  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
BRUTO = RAIZ / "dados" / "bruto"

# Decretos conhecidos, um por ano da faixa que falta, para medir a grafia.
ALVOS = ["42.500", "44.000", "46.000", "48.313", "49.792"]


def main() -> None:
    io = Ioerj()
    medicoes: dict[str, object] = {}
    BRUTO.mkdir(parents=True, exist_ok=True)

    print("[1] busca sem data, por número de decreto")
    por_numero = {}
    for numero in ALVOS:
        materias, total = io.buscar(f"DECRETO {numero}")
        decretos = [m for m in materias if "decreto" in m.tipo.lower()]
        por_numero[numero] = {
            "total_anunciado": total,
            "listadas": len(materias),
            "do_tipo_decreto": len(decretos),
            "amostra": [
                {"id": m.id, "data": m.data, "pagina": m.pagina, "tipo": m.tipo}
                for m in materias[:3]
            ],
        }
        print(
            f"    {numero}: {total or '—'} | listadas {len(materias)} | "
            f"tipo decreto {len(decretos)}"
        )
        if decretos:
            print(f"      1º: {decretos[0].data} p.{decretos[0].pagina} {decretos[0].tipo}")
    medicoes["por_numero"] = por_numero

    print("\n[2] a palavra 'decreto' num dia só (varredura diária)")
    materias, total = io.buscar("decreto", dia="10", mes="01", ano="2023")
    medicoes["um_dia"] = {
        "total_anunciado": total,
        "listadas": len(materias),
        "tipos": sorted({m.tipo for m in materias}),
    }
    print(f"    10/01/2023: {total or '—'} | listadas {len(materias)}")
    print(f"    tipos: {sorted({m.tipo for m in materias})}")

    print("\n[3] o PDF da edição: peso e texto")
    if materias:
        alvo = materias[0]
        pdf = io.pdf_da_edicao(alvo.href_publicacao)
        destino = BRUTO / f"doerj_{alvo.data.replace('/', '')}_p{alvo.pagina}.pdf"
        destino.write_bytes(pdf)
        cabecalho = pdf[:8].decode("latin-1", "replace")
        print(f"    {len(pdf):,} bytes | começa com {cabecalho!r} | {destino.name}")
        medicoes["pdf"] = {
            "bytes": len(pdf),
            "e_pdf": pdf[:4] == b"%PDF",
            "arquivo": destino.name,
        }
        if pdf[:4] == b"%PDF":
            medicoes["pdf"].update(_medir_texto(destino))
    else:
        print("    sem matéria para abrir")

    destino = RAIZ / "medicoes" / "doerj.json"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(json.dumps(medicoes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\ngravado em {destino}")


def _medir_texto(pdf: pathlib.Path) -> dict:
    """Texto nativo ou imagem? `-enc UTF-8` não é opcional: sem ele o pdftotext
    desta máquina escreve Latin-1 e cega toda busca acentuada depois."""
    saida = pdf.with_suffix(".txt")
    try:
        subprocess.run(
            ["pdftotext", "-enc", "UTF-8", str(pdf), str(saida)],
            check=True, capture_output=True, timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"texto": f"pdftotext indisponível: {exc}"}
    texto = saida.read_text(encoding="utf-8", errors="replace")
    paginas = texto.count("\f") or 1
    return {
        "chars": len(texto),
        "paginas": paginas,
        "chars_por_pagina": round(len(texto) / paginas),
        "tem_decreto": texto.upper().count("DECRETO"),
    }


if __name__ == "__main__":
    main()
