"""Coleta as edições do DOERJ, uma por dia, com conferência de completude.

Retomável: o manifesto em `dados/doerj/manifesto.jsonl` registra cada edição
baixada, e a execução seguinte pula o que já está lá. Pode ser interrompida a
qualquer momento.

O QUE ESTA COLETA TEM DE DIFERENTE, E POR QUÊ

O calendário do DOERJ dá **um** link por dia, e nem sempre é a edição inteira.
Medido: em 01/12/2021 o link entregou um PDF de 2 páginas enquanto a busca
mostrava matéria na página 51; em 01/12/2022, 1 página contra 83. Não é erro de
download — é outro caderno, e o arquivo curto chega íntegro, sem nada que
denuncie a falta.

Por isso cada edição é conferida contra a busca do próprio dia: se a maior
página com matéria é maior que o número de páginas do PDF, o que veio não é a
edição toda, e o coletor tenta de novo pelo caminho da busca, que entra pela
matéria e cai na edição certa. Não conseguindo, registra `incompleta` — some do
acervo, não do registro.

O que fica em disco, por dia: o PDF como veio e o texto extraído. Coletar e
processar são fases separadas; nada aqui interpreta decreto.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from ioerj import Ioerj  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
INDICE = RAIZ / "dados" / "calendario.json"
SAIDA = RAIZ / "dados" / "doerj"
MANIFESTO = SAIDA / "manifesto.jsonl"


def ja_coletadas() -> set[str]:
    if not MANIFESTO.exists():
        return set()
    feitas = set()
    for linha in MANIFESTO.read_text("utf-8").splitlines():
        if not linha.strip():
            continue
        reg = json.loads(linha)
        if reg.get("status") in ("ok", "incompleta"):
            feitas.add(reg["data"])
    return feitas


def registrar(reg: dict) -> None:
    with MANIFESTO.open("a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")


def extrair_texto(pdf: pathlib.Path) -> tuple[str, int]:
    txt = pdf.with_suffix(".txt")
    subprocess.run(
        ["pdftotext", "-enc", "UTF-8", str(pdf), str(txt)],
        check=True, capture_output=True, timeout=900,
    )
    texto = txt.read_text(encoding="utf-8", errors="replace")
    return texto, texto.count("\f") or 1


# O campo de busca exige três caracteres — "de" é recusado e devolve zero
# resultado, o que passaria por "edição vazia". Termos frequentes em Parte I,
# tentados em ordem até algum responder.
SONDAS = ("estado", "secretaria", "rio de janeiro")


def materias_do_dia(io: Ioerj, data: str) -> list:
    ano, mes, dia = data.split("-")
    for termo in SONDAS:
        materias, _ = io.buscar(termo, dia=dia, mes=mes, ano=ano)
        if materias:
            return materias
    return []


def maior_pagina_na_busca(materias: list) -> int:
    """Maior página com matéria naquele dia, segundo a busca do site.

    É a régua da completude. A busca tem teto de 100 resultados; para esta
    finalidade não importa — basta uma matéria lá no fim da edição, e o teto só
    subestima, nunca superestima. Subestimar deixa passar edição incompleta;
    superestimar acusaria edição boa de ruim. Erro para o lado certo.
    """
    paginas = [int(m.pagina) for m in materias if m.pagina.isdigit()]
    return max(paginas) if paginas else 0


def main() -> None:
    edicoes = json.loads(INDICE.read_text("utf-8"))
    SAIDA.mkdir(parents=True, exist_ok=True)
    feitas = ja_coletadas()
    pendentes = [e for e in edicoes if e["data"] not in feitas]
    if len(sys.argv) > 1:
        # Um número limita a rodada; datas soltas coletam só aquelas — é como
        # se confere um caso conhecido sem esperar a varredura chegar nele.
        if sys.argv[1].isdigit():
            pendentes = pendentes[: int(sys.argv[1])]
        else:
            alvos = set(sys.argv[1:])
            pendentes = [e for e in edicoes if e["data"] in alvos]
    print(f"{len(edicoes)} edições no índice, {len(feitas)} já coletadas, "
          f"{len(pendentes)} pela frente")

    io = Ioerj(pausa=1.2)
    inicio = time.monotonic()
    for i, ed in enumerate(pendentes, 1):
        data = ed["data"]
        pdf = SAIDA / f"{data}.pdf"
        reg = {"data": data, "uuid": ed["uuid"]}
        try:
            conteudo = io.pdf_por_sessao(ed["sessao"])
            pdf.write_bytes(conteudo)
            texto, paginas = extrair_texto(pdf)
            materias = materias_do_dia(io, data)
            esperado = maior_pagina_na_busca(materias)

            if esperado > paginas:
                # O calendário entregou outro caderno. Entrar pela matéria.
                reg["primeira_tentativa"] = {"paginas": paginas, "esperado": esperado}
                alvo = max(
                    (m for m in materias if m.pagina.isdigit() and m.href_publicacao),
                    key=lambda m: int(m.pagina),
                    default=None,
                )
                if alvo:
                    pdf.write_bytes(io.pdf_da_edicao(alvo.href_publicacao))
                    texto, paginas = extrair_texto(pdf)

            reg.update(
                {
                    "status": "ok" if paginas >= esperado else "incompleta",
                    "bytes": pdf.stat().st_size,
                    "paginas": paginas,
                    "paginas_esperadas": esperado,
                    "chars": len(texto),
                    "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                }
            )
        except Exception as exc:  # noqa: BLE001
            reg.update({"status": "erro", "erro": f"{type(exc).__name__}: {exc}"[:300]})

        registrar(reg)
        if i % 10 == 0 or reg["status"] != "ok":
            decorrido = time.monotonic() - inicio
            resta = (len(pendentes) - i) * decorrido / i / 3600
            print(
                f"[{i}/{len(pendentes)}] {data} {reg['status']} "
                f"{reg.get('paginas', '?')}p / esperado {reg.get('paginas_esperadas', '?')} "
                f"— faltam ~{resta:.1f} h",
                flush=True,
            )

    print("fim")


if __name__ == "__main__":
    main()
