"""Vai buscar, um a um, os decretos que a varredura por edição não trouxe.

POR QUE FALTAM

O calendário do Diário dá **uma edição por dia**, e um dia pode ter mais de
uma: o Decreto 48.313/2023 saiu na "D.O. EXTRA de 10/01/2023", e a edição
normal daquele dia — que foi a coletada — não o traz. Medido pela conferência
de série: 1.220 números ausentes entre 42.200 e 50.410, em 775 blocos
esparsos. Não é um período faltando; é a edição extra de centenas de dias.

COMO SE ACHA O QUE FALTA

A numeração é sequencial, então sei exatamente quais números deviam existir e
não estão. Cada um vira uma consulta dirigida à busca do Diário, que devolve a
matéria e o link da edição em que ela saiu — inclusive as extras, que o
calendário não lista.

DUAS FASES, PORQUE A SEGUNDA É CARA

1. **Localizar**: uma consulta por número, guardando a edição de cada um. É
   barato e dá para repetir.
2. **Baixar**: as edições distintas, uma vez cada. Números consecutivos saem na
   mesma edição, então centenas de decretos custam dezenas de downloads.

Retomável nas duas: o que já foi localizado não se procura de novo.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "processar"))

from ioerj import Ioerj, PARTE_EXECUTIVO  # noqa: E402

import extrair_decretos  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DOERJ = RAIZ / "dados" / "doerj"
FALTANTES = DOERJ / "decretos_faltantes.json"
LOCALIZADOS = DOERJ / "decretos_localizados.jsonl"
EXTRAS = DOERJ / "extras"
SAIDA = DOERJ / "decretos_extras.jsonl"


def com_ponto(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def ja_localizados() -> dict[str, dict]:
    if not LOCALIZADOS.exists():
        return {}
    return {
        json.loads(l)["numero"]: json.loads(l)
        for l in LOCALIZADOS.read_text("utf-8").splitlines()
        if l.strip()
    }


def localizar(io: Ioerj, numeros: list[int]) -> None:
    achados = ja_localizados()
    pendentes = [n for n in numeros if str(n) not in achados]
    print(f"localizar: {len(pendentes)} de {len(numeros)}")
    with LOCALIZADOS.open("a", encoding="utf-8") as f:
        for i, numero in enumerate(pendentes, 1):
            registro = {"numero": str(numero), "materias": []}
            try:
                materias, _ = io.buscar(
                    f'"DECRETO Nº {com_ponto(numero)}"', jornal=PARTE_EXECUTIVO
                )
                # O tipo vem da própria busca: só interessa o normativo.
                for m in materias:
                    if "decreto" in m.tipo.lower():
                        registro["materias"].append(
                            {
                                "data": m.data,
                                "pagina": m.pagina,
                                "tipo": m.tipo,
                                "href": m.href_publicacao,
                            }
                        )
            except Exception as exc:  # noqa: BLE001
                registro["erro"] = f"{type(exc).__name__}: {exc}"[:150]
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
            if i % 25 == 0:
                f.flush()
                print(f"  [{i}/{len(pendentes)}]", flush=True)


def baixar_e_extrair(io: Ioerj) -> None:
    achados = ja_localizados()
    EXTRAS.mkdir(exist_ok=True)

    # Agrupa por edição: números consecutivos saem juntos, e cada edição só
    # precisa ser baixada uma vez.
    por_edicao: dict[str, dict] = {}
    for numero, reg in achados.items():
        for materia in reg.get("materias", []):
            if not materia.get("href"):
                continue
            chave = materia["data"]
            por_edicao.setdefault(chave, {"href": materia["href"], "numeros": set()})
            por_edicao[chave]["numeros"].add(numero)

    print(f"baixar: {len(por_edicao)} edições distintas")
    ja_extraidos = set()
    if SAIDA.exists():
        ja_extraidos = {
            json.loads(l)["data_publicacao"]
            for l in SAIDA.read_text("utf-8").splitlines()
            if l.strip()
        }

    with SAIDA.open("a", encoding="utf-8") as f:
        for i, (data, dados) in enumerate(sorted(por_edicao.items()), 1):
            iso = "-".join(reversed(data.split("/")))
            if iso in ja_extraidos:
                continue
            pdf = EXTRAS / f"{iso}.pdf"
            txt = pdf.with_suffix(".txt")
            try:
                if not txt.exists():
                    pdf.write_bytes(io.pdf_da_edicao(dados["href"]))
                    subprocess.run(
                        ["pdftotext", "-enc", "UTF-8", str(pdf), str(txt)],
                        check=True, capture_output=True, timeout=900,
                    )
                    pdf.unlink()  # o texto basta; o link fica no registro
                texto = txt.read_text(encoding="utf-8", errors="replace")
                for decreto in extrair_decretos.extrair_da_edicao(texto, iso):
                    if decreto["numero"] in dados["numeros"]:
                        decreto["edicao_extra"] = True
                        f.write(json.dumps(decreto, ensure_ascii=False) + "\n")
            except Exception as exc:  # noqa: BLE001
                print(f"  {iso}: {type(exc).__name__}: {exc}"[:120], flush=True)
            if i % 20 == 0:
                f.flush()
                print(f"  [{i}/{len(por_edicao)}]", flush=True)


def main() -> None:
    numeros = json.loads(FALTANTES.read_text("utf-8"))
    io = Ioerj(pausa=1.2)
    if "--so-baixar" not in sys.argv:
        localizar(io, numeros)
    baixar_e_extrair(io)
    print("fim")


if __name__ == "__main__":
    main()
