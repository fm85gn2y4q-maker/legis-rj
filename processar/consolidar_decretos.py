"""Junta tudo o que já se extraiu de decreto e diz o que ainda falta.

Três origens, e elas se acumulam:

    decretos.jsonl          a varredura das 4.454 edições do calendário
    extras/*.txt            os cadernos baixados pela busca por matéria
    cadernos/*.txt          os cadernos alcançados pela recuperação por data

Aqui elas viram uma lista só, e dela sai o que ainda falta na série — que é o
insumo da próxima rodada de recuperação.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import extrair_decretos  # noqa: E402


def ler_caderno(caminho: pathlib.Path) -> str:
    """Lê o caderno esteja ele compactado ou não.

    O texto bruto é grande e comprime cinco para um; quem lê não precisa saber
    em que estado ele está.
    """
    if caminho.suffix == ".gz":
        import gzip

        with gzip.open(caminho, "rt", encoding="utf-8", errors="replace") as f:
            return f.read()
    return caminho.read_text(encoding="utf-8", errors="replace")

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DOERJ = RAIZ / "dados" / "doerj"
CONSOLIDADO = DOERJ / "decretos_todos.jsonl"
FALTAM = DOERJ / "decretos_faltantes.json"


def main() -> None:
    por_numero: dict[str, list[dict]] = {}

    def guardar(reg: dict) -> None:
        por_numero.setdefault(reg["numero"], []).append(reg)

    for linha in (DOERJ / "decretos.jsonl").read_text("utf-8").splitlines():
        if linha.strip():
            guardar(json.loads(linha))
    do_calendario = sum(len(v) for v in por_numero.values())
    print(f"da varredura do calendário: {do_calendario}")

    # `cadernos` fora de `dados/` é o disco interno: desde 25/08/2026 o caderno
    # novo é gravado lá, porque o HD externo caía sob a escrita. As duas pastas
    # valem igual e a consolidação precisa varrer as duas — deixar uma de fora
    # não daria erro, só devolveria um acervo menor.
    pastas = [("extras", DOERJ / "extras"),
              ("cadernos", DOERJ / "cadernos"),
              ("cadernos", RAIZ / "cadernos")]
    for pasta, caminho in pastas:
        if not caminho.exists():
            continue
        antes = sum(len(v) for v in por_numero.values())
        for txt in sorted(list(caminho.glob("*.txt")) + list(caminho.glob("*.txt.gz"))):
            texto = ler_caderno(txt)
            dia = txt.name[:10]
            for decreto in extrair_decretos.extrair_da_edicao(texto, dia):
                decreto["origem"] = pasta
                guardar(decreto)
        print(f"de {pasta}: +{sum(len(v) for v in por_numero.values()) - antes}")

    with CONSOLIDADO.open("w", encoding="utf-8") as f:
        for ocorrencias in por_numero.values():
            for reg in ocorrencias:
                f.write(json.dumps(reg, ensure_ascii=False) + "\n")

    numeros = {int(n) for n in por_numero if n.isdigit() and int(n) < 60000}

    # O TOPO DA SÉRIE NÃO PODE SER DECIDIDO POR UM REGISTRO SÓ
    #
    # A cobertura declarada é `fim - inicio` menos o que se tem, então um único
    # número alto e falso inventa milhares de ausentes. Aconteceu: o Decreto
    # 53.879 do **Prefeito** do Rio, citado dentro de um ato estadual, subiu o
    # teto de 50.431 para 53.879 e a lacuna declarada foi de 4,9% para 32,1%.
    # O extrator agora recusa ato de outra autoridade, mas o número seguinte a
    # escapar não pode passar calado — daí a conferência aqui, que não descarta
    # nada: só grita.
    ordenados = sorted(numeros, reverse=True)
    if len(ordenados) > 1 and ordenados[0] - ordenados[1] > 200:
        print(
            f"  !! ATENÇÃO: {ordenados[0]} está {ordenados[0] - ordenados[1]} "
            f"acima do seguinte ({ordenados[1]}). Se for falso positivo, ele "
            f"sozinho inventa {ordenados[0] - ordenados[1]} ausentes. Confira "
            f"antes de acreditar na cobertura."
        )
    inicio, fim = 42200, max(numeros)
    faltam = [n for n in range(inicio, fim + 1) if n not in numeros]
    FALTAM.write_text(json.dumps(faltam), encoding="utf-8")

    # A lacuna vai para o servidor declarar. Não basta dizer "não achei": o
    # acervo sabe que 224 dos ausentes EXISTEM, porque outros atos os citam —
    # um deles 13.754 vezes. Dizer "não encontrei" sobre um decreto que sustenta
    # milhares de despachos é diferente de dizer "não existe", e a diferença é
    # justamente o que um acervo jurídico não pode confundir.
    citados = {}
    prova = RAIZ / "medicoes" / "ausentes_citados.json"
    if prova.exists():
        citados = json.loads(prova.read_text("utf-8")).get("detalhe", {})
    comprovados = [n for n in faltam if str(n) in citados]
    (DOERJ / "lacuna.json").write_text(
        json.dumps(
            {
                "serie": f"{inicio}-{fim}",
                "numeros_na_serie": fim - inicio + 1,
                "no_acervo": (fim - inicio + 1) - len(faltam),
                "ausentes": len(faltam),
                "ausentes_com_existencia_comprovada": len(comprovados),
                "mais_citados": sorted(
                    ((n, citados[str(n)]) for n in comprovados),
                    key=lambda x: -x[1],
                )[:10],
                "atualizado_em": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nnúmeros distintos: {len(numeros)}")
    print(f"série {inicio}–{fim}: faltam {len(faltam)} "
          f"({100 * len(faltam) / (fim - inicio + 1):.1f}%)")
    print(f"lista em {FALTAM}")


if __name__ == "__main__":
    main()
