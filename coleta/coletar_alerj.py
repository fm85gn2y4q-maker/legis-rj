"""Coleta a legislação da ALERJ, em duas fases retomáveis.

    Fase A — índice: varre a busca por número e acumula os atos encontrados.
    Fase B — documentos: baixa o HTML de cada ato ainda não baixado.

POR QUE VARRER NÚMERO A NÚMERO

Porque não há como percorrer as views: qualquer URL com `Start=` ou `Count=`
derruba a conexão (ver `alerj.py`). Sobra a busca, e ela tem teto de 1.000
resultados — então a varredura precisa de uma partição em que nenhuma consulta
chegue perto disso. O número do ato é essa partição.

O que a partição por número tem de bom, além de caber no teto: ela **não
depende da espécie**. Uma consulta por `232` devolve a lei ordinária 232, a lei
complementar 232, a resolução 232 e tudo o que as cite. Varrendo 1 até o maior
número da maior série, passa-se por todas as séries de uma vez.

E o que ela tem de traiçoeiro: o número exige ponto de milhar (`11.293` acha,
`11293` não acha nada), e a busca não é por campo — traz também quem cita.
Por isso o índice guarda o que veio e deixa a identificação do ato para a fase
de processamento, que lê o cabeçalho do documento. Coletar e processar são
fases separadas.

ONDE A PARTIÇÃO NÃO SEGURA — E O QUE FAZER

Medido ao experimentar: os números de **1 a 8 estouraram o teto de 1.000, todos
os oito**. Número curto aparece em citação por todo o acervo, e a consulta volta
cheia de atos que só o mencionam. Se o próprio ato nº 3 não estiver entre os
1.000 devolvidos, ele não entra — e nada avisa.

Não adianta refinar o padrão: o remédio é conferir depois. A série de cada
espécie é sequencial, então, terminada a varredura, sabe-se exatamente quais
números deviam existir e não apareceram. Esses poucos voltam para a busca
combinados com o ano (`ConectorProposicao=And` mais o ano em `Busca`), que
parte o resultado em pedaços que cabem no teto.

Por isso `truncadas` é registrado no progresso: é a lista de onde procurar
buraco, não um aviso decorativo.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from alerj import Alerj  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "dados" / "alerj"
DOCS = SAIDA / "docs"
INDICE = SAIDA / "indice.jsonl"
PROGRESSO = SAIDA / "progresso.json"

# Topo de cada série em 04/08/2026 (medido em inventario.py). A maior manda:
# varrendo 1..11.293 passa-se por todos os números de todas as espécies.
MAIOR_NUMERO = 11_293
TETO_DA_BUSCA = 1_000


def com_ponto(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def carregar_indice() -> dict[str, dict]:
    if not INDICE.exists():
        return {}
    achados = {}
    for linha in INDICE.read_text("utf-8").splitlines():
        if linha.strip():
            reg = json.loads(linha)
            achados[reg["unid"]] = reg
    return achados


def fase_a(a: Alerj, indice: dict[str, dict], ate: int = MAIOR_NUMERO) -> None:
    progresso = (
        json.loads(PROGRESSO.read_text("utf-8")) if PROGRESSO.exists() else {}
    )
    inicio_em = progresso.get("ultimo_numero", 0) + 1
    truncadas = progresso.get("truncadas", [])
    print(f"fase A: números {inicio_em}..{ate}, {len(indice)} atos no índice")

    t0 = time.monotonic()
    with INDICE.open("a", encoding="utf-8") as f:
        for n in range(inicio_em, ate + 1):
            try:
                achados = a.buscar(numero=com_ponto(n))
            except Exception as exc:  # noqa: BLE001
                print(f"  {n}: {type(exc).__name__}: {exc}", flush=True)
                continue

            if len(achados) >= TETO_DA_BUSCA:
                # Consulta truncada: o que passar de 1.000 se perdeu, e o site
                # não avisa. Fica registrado para tratamento à parte.
                truncadas.append(n)

            novos = 0
            for r in achados:
                if r.unid in indice:
                    continue
                reg = {
                    "unid": r.unid,
                    "caminho": r.caminho,
                    "colunas": r.colunas,
                    "achado_em": com_ponto(n),
                }
                indice[r.unid] = reg
                f.write(json.dumps(reg, ensure_ascii=False) + "\n")
                novos += 1

            if n % 25 == 0:
                f.flush()
                PROGRESSO.write_text(
                    json.dumps(
                        {"ultimo_numero": n, "truncadas": truncadas},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                decorrido = time.monotonic() - t0
                feitos = n - inicio_em + 1
                resta = (ate - n) * decorrido / feitos / 3600
                print(
                    f"  [{n}/{ate}] {len(indice)} atos "
                    f"(+{novos} neste) — faltam ~{resta:.1f} h",
                    flush=True,
                )

    PROGRESSO.write_text(
        json.dumps(
            {"ultimo_numero": ate, "truncadas": truncadas},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"fase A concluída: {len(indice)} atos, {len(truncadas)} consultas truncadas")


def fase_b(a: Alerj, indice: dict[str, dict]) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    pendentes = [r for r in indice.values() if not (DOCS / f"{r['unid']}.html").exists()]
    print(f"fase B: {len(pendentes)} documentos a baixar de {len(indice)}")

    t0 = time.monotonic()
    for i, reg in enumerate(pendentes, 1):
        destino = DOCS / f"{reg['unid']}.html"
        try:
            html = a.documento("https://alerjln1.alerj.rj.gov.br" + reg["caminho"])
            destino.write_text(html, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"  {reg['unid']}: {type(exc).__name__}: {exc}"[:200], flush=True)
            continue
        if i % 50 == 0:
            decorrido = time.monotonic() - t0
            resta = (len(pendentes) - i) * decorrido / i / 3600
            print(f"  [{i}/{len(pendentes)}] — faltam ~{resta:.1f} h", flush=True)

    print("fase B concluída")


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    a = Alerj(pausa=1.2)
    indice = carregar_indice()
    ate = MAIOR_NUMERO
    if "--ate" in sys.argv:
        ate = int(sys.argv[sys.argv.index("--ate") + 1])
    if "--so-documentos" not in sys.argv:
        fase_a(a, indice, ate)
        indice = carregar_indice()
    fase_b(a, indice)


if __name__ == "__main__":
    main()
