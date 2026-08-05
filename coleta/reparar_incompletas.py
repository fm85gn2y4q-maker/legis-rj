"""Repara os dias que a coleta não conseguiu fechar.

O desvio da coleta escolhe a matéria de **maior página** para entrar na edição,
supondo que ela esteja no caderno mais gordo. Medido: nem sempre. Nesses dias a
matéria de maior página estava num suplemento de duas páginas, e era o
suplemento que vinha — ficando registrado como `incompleta`, corretamente.

Aqui a escolha é outra e mais cara: abre-se o caderno de **várias** matérias
espalhadas pelo dia, junta-se os identificadores distintos e fica-se com o
maior arquivo. É lento demais para os 4.455 dias e certeiro para a dúzia que
sobrou.

Serve também para o dia em que o calendário não devolve PDF nenhum: ali não há
o que comparar, e qualquer caderno alcançável é melhor que nada.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from ioerj import Ioerj, _chave_do_pdf, _decodifica  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DOERJ = RAIZ / "dados" / "doerj"
MANIFESTO = DOERJ / "manifesto.jsonl"


def cadernos_do_dia(io: Ioerj, data: str, quantos: int = 8) -> dict[str, str]:
    """Identificadores distintos de caderno alcançáveis naquele dia."""
    ano, mes, dia = data.split("-")
    materias = []
    for termo in ("estado", "secretaria", "rio de janeiro"):
        materias, _ = io.buscar(termo, dia=dia, mes=mes, ano=ano)
        if materias:
            break
    comlink = sorted(
        (m for m in materias if m.href_publicacao and m.pagina.isdigit()),
        key=lambda m: int(m.pagina),
    )
    if not comlink:
        return {}
    passo = max(1, len(comlink) // quantos)
    achados: dict[str, str] = {}
    for m in comlink[::passo][:quantos]:
        try:
            html = _decodifica(io._pedir(io._visualizador(m.href_publicacao)).content)
        except Exception:  # noqa: BLE001
            continue
        u = re.search(r'var pd = "([^"]+)"', html)
        if u:
            achados.setdefault(u.group(1), m.pagina)
    return achados


def main() -> None:
    registros = {}
    for linha in MANIFESTO.read_text("utf-8").splitlines():
        if linha.strip():
            r = json.loads(linha)
            # A expectativa de páginas vem da primeira passada; o reparo não a
            # recalcula, e não pode deixá-la se perder no caminho.
            if r["data"] in registros and not r.get("paginas_esperadas"):
                r["paginas_esperadas"] = registros[r["data"]].get("paginas_esperadas")
            registros[r["data"]] = r
    datas = sys.argv[1:] or [
        d for d, r in registros.items() if r.get("status") != "ok"
    ]
    print(f"reparando {len(datas)} dias: {datas}")

    io = Ioerj(pausa=1.2)
    for data in datas:
        anterior = registros.get(data, {})
        cadernos = cadernos_do_dia(io, data)
        print(f"{data}: {len(cadernos)} caderno(s) alcançável(is)")
        melhor = (0, None, None)  # bytes, conteúdo, uuid
        for uuid in cadernos:
            try:
                conteudo = io._baixar_pdf(_chave_do_pdf(uuid))
            except Exception as exc:  # noqa: BLE001
                print(f"    {uuid[:8]}…: {type(exc).__name__}")
                continue
            print(f"    {uuid[:8]}…: {len(conteudo):,} bytes")
            if len(conteudo) > melhor[0]:
                melhor = (len(conteudo), conteudo, uuid)

        if not melhor[1]:
            print("    nada baixável; fica como está")
            continue

        pdf = DOERJ / f"{data}.pdf"
        pdf.write_bytes(melhor[1])
        txt = pdf.with_suffix(".txt")
        subprocess.run(
            ["pdftotext", "-enc", "UTF-8", str(pdf), str(txt)],
            check=True, capture_output=True, timeout=900,
        )
        texto = txt.read_text(encoding="utf-8", errors="replace")
        paginas = texto.count("\f") or 1
        # Não promover a "ok" o que continua abaixo do esperado: o reparo
        # prova que não há caderno melhor alcançável, não que a edição veio
        # inteira. Marcar ok aqui apagaria a única pista de que falta página.
        esperado = anterior.get("paginas_esperadas") or 0
        reg = {
            "data": data,
            "uuid": melhor[2],
            "status": "ok" if paginas >= esperado else "incompleta",
            "reparado": True,
            "esgotou_os_cadernos": True,
            "bytes": len(melhor[1]),
            "paginas": paginas,
            "paginas_esperadas": esperado,
            "chars": len(texto),
            "sha256": hashlib.sha256(melhor[1]).hexdigest(),
        }
        with MANIFESTO.open("a", encoding="utf-8") as f:
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
        print(f"    ficou com {melhor[2][:8]}… — {paginas} páginas, {len(texto):,} chars")


if __name__ == "__main__":
    main()
