"""Descarta o PDF de cada edição, **depois** de garantir o link de conferência.

O texto é 12% do peso e é dele que o acervo vive; os 20 GB de PDF são cópia do
que a Imprensa Oficial serve. Só que apagar a cópia transfere para o link uma
responsabilidade que ele não tinha: sem PDF local, **o link é a única forma de
conferir o que o acervo afirma**. Numa peça, citação sem conferência não vale.

Por isso nada é apagado sem três garantias, nesta ordem:

1. **O link certo.** Para a maioria dos dias é o identificador do calendário.
   Mas nos dias em que o calendário entregou caderno parcial e a coleta desviou
   pela busca, o identificador do calendário aponta para o arquivo **errado** —
   o de uma página. Esses são refeitos pelo mesmo caminho da coleta, e o link
   gravado é o da edição que está no acervo.
2. **O link responde.** Conferido um a um, lendo só os primeiros 4 KB e
   abortando: confirma que ainda vem PDF, e custa 4 KB em vez de 5 MB.
3. **O texto presta.** Arquivo existe e tem densidade de página compatível com
   texto nativo. Extração vazia ou truncada retém o PDF.

Falhando qualquer uma, o PDF **fica**. O que sobra é `dados/doerj/edicoes.jsonl`,
o índice que o servidor vai usar para citar.

Sobre o sha256 que a coleta gravou: ele registra o que foi recebido, e **não**
serve para reconferir depois. O servidor remonta o PDF a cada pedido e o
arquivo sai com alguns bytes de diferença — medido: 4.850.546 na coleta e
4.850.542 no dia seguinte, mesma edição.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from ioerj import BASE, UA, Ioerj, _chave_do_pdf, _decodifica  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DOERJ = RAIZ / "dados" / "doerj"
MANIFESTO = DOERJ / "manifesto.jsonl"
CALENDARIO = RAIZ / "dados" / "calendario.json"
EDICOES = DOERJ / "edicoes.jsonl"

DENSIDADE_MINIMA = 500  # caracteres por página; nativo dá 10 mil a 20 mil


def link_de(uuid: str) -> str:
    return f"{BASE}/mostra_edicao.php?k={_chave_do_pdf(uuid)}"


def carregar_manifesto() -> dict[str, dict]:
    """A última linha de cada data manda — o manifesto é append-only."""
    registros: dict[str, dict] = {}
    for linha in MANIFESTO.read_text("utf-8").splitlines():
        if linha.strip():
            reg = json.loads(linha)
            registros[reg["data"]] = reg
    return registros


def ja_enxugadas() -> set[str]:
    if not EDICOES.exists():
        return set()
    return {
        json.loads(l)["data"]
        for l in EDICOES.read_text("utf-8").splitlines()
        if l.strip()
    }


# `edicoes.jsonl` é append-only, como o manifesto: quando um dia é refeito
# (reparo de edição incompleta, por exemplo), a linha nova fica valendo e a
# antiga permanece como histórico. Quem lê o índice tem de ficar com a última
# linha de cada data — ler a primeira devolve o link de antes do reparo, que
# aponta para o caderno errado.


def link_da_edicao_desviada(io: Ioerj, data: str) -> str:
    """Refaz o caminho da busca para achar o identificador do caderno certo."""
    import re

    ano, mes, dia = data.split("-")
    for termo in ("estado", "secretaria", "rio de janeiro"):
        materias, _ = io.buscar(termo, dia=dia, mes=mes, ano=ano)
        alvo = max(
            (m for m in materias if m.pagina.isdigit() and m.href_publicacao),
            key=lambda m: int(m.pagina),
            default=None,
        )
        if alvo:
            html = _decodifica(io._pedir(io._visualizador(alvo.href_publicacao)).content)
            achado = re.search(r'var pd = "([^"]+)"', html)
            if achado:
                return link_de(achado.group(1))
    return ""


def confere(sessao: requests.Session, url: str) -> bool:
    """Lê os primeiros 4 KB e aborta. Chave inválida devolve text/html.

    O intervalo é aqui e não no `Ioerj` porque esta conferência usa sessão
    própria: sem ele, seriam 4.455 pedidos sem pausa nenhuma, ao mesmo tempo em
    que a coleta ainda está baixando edições do mesmo servidor.
    """
    time.sleep(0.8)
    try:
        with sessao.get(url, stream=True, timeout=120) as r:
            if r.headers.get("Content-Type", "") != "application/pdf":
                return False
            for pedaco in r.iter_content(4096):
                return pedaco.startswith(b"%PDF")
    except requests.RequestException:
        return False
    return False


def main() -> None:
    manifesto = carregar_manifesto()
    calendario = {e["data"]: e for e in json.loads(CALENDARIO.read_text("utf-8"))}
    feitas = ja_enxugadas()

    pendentes = [
        reg
        for data, reg in sorted(manifesto.items())
        if data not in feitas and reg.get("status") in ("ok", "incompleta")
    ]
    argumentos = [a for a in sys.argv[1:] if a != "--refazer"]
    if argumentos:
        if argumentos[0].isdigit():
            pendentes = pendentes[: int(argumentos[0])]
        else:
            # Datas soltas. Com `--refazer`, passa por cima do índice: é como
            # se corrige o dia que foi enxugado antes de a coleta ser reparada,
            # e cujo link no índice aponta para o caderno velho.
            alvos = set(argumentos)
            pendentes = [
                r
                for r in manifesto.values()
                if r["data"] in alvos
                and ("--refazer" in sys.argv or r["data"] not in feitas)
            ]
    print(f"{len(pendentes)} edições a conferir e enxugar")

    io = Ioerj(pausa=1.0)
    sessao = requests.Session()
    sessao.headers["User-Agent"] = UA
    liberado = retido = 0
    t0 = time.monotonic()

    with EDICOES.open("a", encoding="utf-8") as saida:
        for i, reg in enumerate(pendentes, 1):
            data = reg["data"]
            pdf, txt = DOERJ / f"{data}.pdf", DOERJ / f"{data}.txt"
            item = {
                "data": data,
                "paginas": reg.get("paginas"),
                "chars": reg.get("chars"),
                "sha256_recebido": reg.get("sha256"),
            }

            # 1. o link certo
            if reg.get("reparado"):
                # O reparo abriu vários cadernos e escolheu um; o identificador
                # que ele gravou é o do arquivo que está em disco. Cair no
                # calendário aqui grava link para outro caderno — medido em
                # 02/02/2023, onde o calendário aponta 6253E6AC e o acervo tem
                # 47E6F87A.
                item["link"] = link_de(reg["uuid"])
                item["origem_do_link"] = "reparo"
            elif reg.get("primeira_tentativa"):
                # Refazer o caminho da busca é a parte frágil: depende de rede
                # e o servidor derruba conexão. Falhando, o PDF fica — perder
                # espaço é reversível, perder a conferência não.
                try:
                    item["link"] = link_da_edicao_desviada(io, data)
                except Exception as exc:  # noqa: BLE001
                    item["link"] = ""
                    item["erro"] = f"{type(exc).__name__}: {exc}"[:200]
                item["origem_do_link"] = "busca"
            elif data in calendario:
                item["link"] = link_de(calendario[data]["uuid"])
                item["origem_do_link"] = "calendario"
            else:
                item["link"] = ""
                item["origem_do_link"] = "ausente"

            # 2. o link responde  3. o texto presta
            densidade = (reg.get("chars") or 0) / max(reg.get("paginas") or 1, 1)
            item["link_confere"] = bool(item["link"]) and confere(sessao, item["link"])
            item["texto_presta"] = txt.exists() and densidade >= DENSIDADE_MINIMA
            item["densidade"] = round(densidade)

            if item["link_confere"] and item["texto_presta"]:
                if pdf.exists():
                    item["bytes_liberados"] = pdf.stat().st_size
                    pdf.unlink()
                item["pdf"] = "descartado"
                liberado += 1
            else:
                item["pdf"] = "retido"
                retido += 1
                print(
                    f"  RETIDO {data}: link={item['link_confere']} "
                    f"texto={item['texto_presta']} densidade={item['densidade']}",
                    flush=True,
                )

            item["conferido_em"] = time.strftime("%Y-%m-%d")
            saida.write(json.dumps(item, ensure_ascii=False) + "\n")

            if i % 50 == 0:
                saida.flush()
                resta = (len(pendentes) - i) * (time.monotonic() - t0) / i / 3600
                print(
                    f"[{i}/{len(pendentes)}] {liberado} descartados, "
                    f"{retido} retidos — faltam ~{resta:.1f} h",
                    flush=True,
                )

    print(f"\n{liberado} PDFs descartados, {retido} retidos. Índice em {EDICOES}")


if __name__ == "__main__":
    main()
