"""Recupera os decretos cuja publicação não está indexada na busca do Diário.

O PROBLEMA

224 decretos existem — são citados por outros atos, um deles 13.754 vezes — e
a busca do Diário não devolve a publicação original de nenhum. Testado: para o
Decreto 47.653 ela devolve seis matérias, todas apenas **citando** o decreto.
E o texto local das edições do dia não traz o número: a publicação está num
caderno que nem o calendário nem a busca alcançam.

O CAMINHO

A data sai de duas fontes, e a segunda é melhor que a primeira.

A citação administrativa às vezes traz a data — "Decreto nº 44.251, de 17 de
junho de 2013" —, mas só 56 dos 300 são citados assim; o resto aparece como
"Decreto nº 48.259/2022", sem dia.

O que resolve para **todos** é a numeração ser cronológica: o decreto 48.259
foi assinado entre o 48.258 e o 48.260, e esses dois estão no acervo com data.
Medido: os 312 ausentes são cercados por vizinhos, com janela **mediana de 2
dias** — 291 deles cabem em sete dias ou menos.

Com a janela, procura-se **qualquer matéria publicada naqueles dias**: cada uma
leva ao caderno em que saiu, e cadernos diferentes do mesmo dia se alcançam por
matérias diferentes. Baixando os cadernos que aparecerem, o decreto pode estar
num deles.

Não há garantia. É por isso que o resultado é registrado ato a ato: recuperado,
ou procurado e não achado — que também é informação, e melhor que silêncio.

O decreto sai publicado no dia seguinte ao da assinatura, às vezes dois ou três
depois. A janela vai da própria data a cinco dias adiante.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
from datetime import date, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "processar"))

from ioerj import PARTE_EXECUTIVO, Ioerj  # noqa: E402
from ferramentas import PDFTOTEXT  # noqa: E402

import extrair_decretos  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DOERJ = RAIZ / "dados" / "doerj"
DATAS = DOERJ / "datas_dos_ausentes.json"
CADERNOS = DOERJ / "cadernos"
RESULTADO = DOERJ / "decretos_recuperados.jsonl"
TENTADOS = DOERJ / "decretos_tentados.json"

FOLGA = 3  # dias além do cerco: o ato sai publicado depois de assinado
MATERIAS_POR_DIA = 4  # cadernos distintos que se tenta alcançar por dia
JANELA_MAXIMA = 12  # além disso o cerco não ajuda e o custo explode


def _data(bruto: str | None):
    try:
        return date.fromisoformat(bruto or "")
    except ValueError:
        return None


def datas_conhecidas() -> dict[int, date]:
    """Número → data, do que já foi extraído. É o que cerca os ausentes."""
    mapa: dict[int, date] = {}
    for linha in (DOERJ / "decretos.jsonl").read_text("utf-8").splitlines():
        if not linha.strip():
            continue
        reg = json.loads(linha)
        quando = _data(reg.get("data"))
        if quando:
            mapa.setdefault(int(reg["numero"]), quando)
    return mapa


def janela_do_ausente(numero: int, conhecidas: dict[int, date]) -> list[str]:
    """Dias em que a publicação pode estar, pelo cerco dos vizinhos."""
    antes = next(
        (conhecidas[k] for k in range(numero - 1, numero - 40, -1) if k in conhecidas),
        None,
    )
    depois = next(
        (conhecidas[k] for k in range(numero + 1, numero + 40) if k in conhecidas),
        None,
    )
    if not (antes and depois) or (depois - antes).days > JANELA_MAXIMA:
        return []
    fim = depois + timedelta(days=FOLGA)
    return [
        (antes + timedelta(days=n)).isoformat()
        for n in range((fim - antes).days + 1)
    ]


def texto_do_caderno(io: Ioerj, href: str, apelido: str) -> str | None:
    """Baixa o caderno daquela matéria e devolve o texto. O PDF não fica."""
    CADERNOS.mkdir(exist_ok=True)
    txt = CADERNOS / f"{apelido}.txt"
    if txt.exists():
        return txt.read_text(encoding="utf-8", errors="replace")
    pdf = CADERNOS / f"{apelido}.pdf"
    try:
        pdf.write_bytes(io.pdf_da_edicao(href))
        subprocess.run(
            [PDFTOTEXT, "-enc", "UTF-8", str(pdf), str(txt)],
            check=True, capture_output=True, timeout=900,
        )
    except Exception:  # noqa: BLE001
        return None
    finally:
        if pdf.exists():
            pdf.unlink()
    return txt.read_text(encoding="utf-8", errors="replace") if txt.exists() else None


def main() -> None:
    conhecidas = datas_conhecidas()
    ausentes = json.loads((DOERJ / "decretos_sem_materia.json").read_text("utf-8"))
    tentados = json.loads(TENTADOS.read_text("utf-8")) if TENTADOS.exists() else {}
    io = Ioerj(pausa=1.2)

    pendentes = [str(n) for n in ausentes if str(n) not in tentados]
    print(f"recuperar: {len(pendentes)} de {len(alvos)}")
    achados = 0

    with RESULTADO.open("a", encoding="utf-8") as saida:
        for i, numero in enumerate(pendentes, 1):
            dias = janela_do_ausente(int(numero), conhecidas)
            registro = {"numero": numero, "janela": [dias[0], dias[-1]] if dias else []}
            encontrado = None

            for dia in dias:
                ano, mes, d = dia.split("-")
                try:
                    materias, _ = io.buscar(
                        "de", jornal=PARTE_EXECUTIVO, dia=d, mes=mes, ano=ano
                    )
                except Exception as exc:  # noqa: BLE001
                    registro.setdefault("erros", []).append(f"{dia}: {exc}"[:80])
                    continue
                com_link = [m for m in materias if m.href_publicacao]
                # Matérias de páginas bem diferentes tendem a estar em cadernos
                # diferentes — é assim que se alcança o caderno que falta.
                com_link.sort(key=lambda m: int(m.pagina) if m.pagina.isdigit() else 0)
                passo = max(1, len(com_link) // MATERIAS_POR_DIA)
                for materia in com_link[::passo][:MATERIAS_POR_DIA]:
                    apelido = f"{dia}-p{materia.pagina}"
                    texto = texto_do_caderno(io, materia.href_publicacao, apelido)
                    if not texto:
                        continue
                    for decreto in extrair_decretos.extrair_da_edicao(texto, dia):
                        if decreto["numero"] == numero:
                            decreto["recuperado_de"] = apelido
                            saida.write(json.dumps(decreto, ensure_ascii=False) + "\n")
                            encontrado = apelido
                            break
                    if encontrado:
                        break
                if encontrado:
                    break

            registro["encontrado"] = encontrado
            tentados[numero] = registro
            if encontrado:
                achados += 1
            if i % 10 == 0:
                saida.flush()
                TENTADOS.write_text(
                    json.dumps(tentados, ensure_ascii=False), encoding="utf-8"
                )
                print(f"  [{i}/{len(pendentes)}] recuperados {achados}", flush=True)

    TENTADOS.write_text(json.dumps(tentados, ensure_ascii=False), encoding="utf-8")
    print(f"\nrecuperados {achados} de {len(pendentes)}")


if __name__ == "__main__":
    main()
