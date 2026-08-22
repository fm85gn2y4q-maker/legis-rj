"""Extrai os decretos do Executivo do texto das edições do Diário Oficial.

O QUE É UM REGISTRO AQUI

Não é a edição: é o ato. Uma edição da Parte I traz dezenas deles emendados
num texto corrido, e delimitar errado não dá erro — dá um decreto com o texto
do vizinho colado no fim, que é pior, porque parece certo.

DUAS COISAS COM O MESMO RÓTULO

    DECRETO Nº 48.310 DE 09 DE JANEIRO DE 2023   ← normativo, numerado
    DECRETO DE 09 DE JANEIRO DE 2023             ← de pessoal, sem número

O segundo é nomeação e exoneração. Medido em 300 edições: 667 numerados contra
296 cabeçalhos de pessoal. Só o numerado entra: é o que se cita.

VALIDAR ANTES DE DELIMITAR

A regra que custou caro no acervo de Mesquita, e vale igual aqui: um candidato
que o parser descarta **depois** já serviu de fronteira para o anterior. Aqui
os candidatos são todos validados primeiro, e só os que sobrevivem delimitam.

O que valida um cabeçalho de verdade, além de começar linha:

  - abaixo dele vem a fórmula do ato — `O GOVERNADOR DO ESTADO`, `DECRETA`,
    ou o `D E C R E T A` de letras espaçadas que a diagramação usa;
  - ou vem uma ementa em caixa alta, que é como todo decreto normativo abre.

Sem isso, "DECRETO Nº 48.310" no começo de uma linha pode ser citação dentro de
outro ato — e é, com frequência, em ato que altera decreto anterior.

REPUBLICAÇÃO

O mesmo número sai em mais de uma edição: medido, 26 em 300 edições. O Diário
publica com incorreção e republica dias depois, e **nada no texto da primeira
avisa**. Cada ocorrência é gravada com sua data de publicação; quem responde
fica com a última, e diz que houve republicação.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DOERJ = RAIZ / "dados" / "doerj"
SAIDA = DOERJ / "decretos.jsonl"

MESES = {
    "JANEIRO": 1, "FEVEREIRO": 2, "MARCO": 3, "MARÇO": 3, "ABRIL": 4,
    "MAIO": 5, "JUNHO": 6, "JULHO": 7, "AGOSTO": 8, "SETEMBRO": 9,
    "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12,
}

CABECALHO = re.compile(
    r"^DECRETO\s+N[ºO°]?\s*(\d[\d.]*)\s+DE\s+(\d{1,2})[ºo°]?\s+DE\s+"
    r"([A-ZÇÃÉÊÍÓÔÕÚ]+)\s+DE\s+(\d{4})",
    re.MULTILINE,
)

# Fórmula de abertura. O `D E C R E T A` espaçado é diagramação, não erro de
# extração: aparece assim no PDF.
ABERTURA = re.compile(
    r"(O\s+GOVERNADOR\s+DO\s+ESTADO|D\s*E\s*C\s*R\s*E\s*T\s*A|"
    r"A\s+GOVERNADORA\s+DO\s+ESTADO)",
    re.IGNORECASE,
)
def parece_ementa(linha: str) -> bool:
    """Ementa é a linha em caixa alta logo abaixo do cabeçalho.

    Testar por lista de caracteres permitidos falha por acento faltando — foi
    o que aconteceu: a classe não tinha `Á`, e "E DÁ OUTRAS PROVIDÊNCIAS"
    derrubava a linha inteira. Compara-se com a própria maiúscula, que não tem
    lista para esquecer.
    """
    limpa = linha.strip()
    if len(limpa) < 25:
        return False
    letras = [c for c in limpa if c.isalpha()]
    return bool(letras) and limpa == limpa.upper()

# O Diário fecha cada matéria com o identificador dela — `Id: 2450955`. É a
# fronteira boa, e existe em toda edição de 2008 a 2026 (medido em amostra de
# doze anos: de 73 a 277 marcas por edição).
#
# Mas ela **cai no meio da frase**: a diagramação é em duas colunas, e o
# pdftotext intercala o rodapé de uma coluna no corpo da outra. Medido no
# Decreto 48.310/2023 — a primeira marca aparece em "...os Entes Vinculados
# relacionados na estrutura / Id: 2450942 / abaixo, da Secretaria...". Parar
# nela cortaria o decreto de 11.793 para 877 caracteres, no meio de uma
# oração, e o pedaço perdido é justamente o anexo.
#
# O que distingue a marca verdadeira: depois dela **não continua o texto**.
# Marca seguida de minúscula é rodapé intercalado; marca seguida de maiúscula,
# de linha em branco ou do fim do trecho é fim de matéria.
#
# E vale a **primeira** limpa, não a última: no último decreto da edição o
# trecho vai até o fim do arquivo, e ficar com a última marca fez um decreto de
# 345 mil caracteres — a edição inteira dentro de um ato só.
FIM_DA_MATERIA = re.compile(r"Id:\s*\d+")


# Menor corpo plausível de um decreto: ementa, fórmula do Governador, um artigo
# e a assinatura. Abaixo disso não é decreto — é cabeçalho órfão.
CORPO_MINIMO = 300


def fim_de_materia(texto: str, inicio: int, limite: int) -> int | None:
    """Posição da marca que realmente encerra a matéria, se houver.

    Duas exclusões, e cada uma corresponde a um jeito de a diagramação em duas
    colunas se intercalar no texto:

    1. **Marca seguida de minúscula** é rodapé de uma coluna caído no meio de
       uma frase da outra. Medido no Decreto 48.310/2023: parar nela cortava o
       ato de 11.793 para 877 caracteres, no meio de uma oração.

    2. **Marca colada ao cabeçalho** é o fim da matéria *anterior*, que a
       coluna despejou logo abaixo do título da seguinte. Medido no Decreto
       48.515/2023: o `Id: 2480908` aparece entre o cabeçalho e a ementa, é
       seguido de maiúscula — passa no teste 1 — e produzia um decreto de 39
       caracteres, só o título. Eram 169 assim.

    O que sustenta o corte é o fato de domínio: um decreto tem ementa, fórmula
    e artigo. Não cabe em 39 caracteres.
    """
    for marca in FIM_DA_MATERIA.finditer(texto, inicio, limite):
        depois = texto[marca.end() : marca.end() + 60].lstrip()
        if depois and depois[0].islower():
            continue
        if marca.start() - inicio < CORPO_MINIMO:
            continue
        return marca.start()
    return None

# Outro ato começando: serve de fronteira mesmo não sendo decreto.
OUTRO_ATO = re.compile(
    r"^(LEI\s+N|LEI\s+COMPLEMENTAR|RESOLU[ÇC][ÃA]O\s+|PORTARIA\s+|DELIBERA[ÇC][ÃA]O\s+|"
    r"ATO\s+D[OE]\s+|AVISO\s+|EDITAL\s+|EXTRATO\s+|DESPACHO\s+|"
    r"DECRETOS?\s+DE\s+\d{1,2}\s+DE\s+)",
    re.MULTILINE,
)

# Faixa plausível: a série estadual passa de 30.000 nos anos 2000 e chega perto
# de 49.800 hoje. Número de quatro dígitos ou menos, em edição recente, é
# citação de decreto antigo — não cabeçalho.
MENOR_NUMERO_PLAUSIVEL = 10_000


def valida(texto: str, inicio: int, fim_cabecalho: int) -> bool:
    """Cabeçalho de verdade, ou citação com a mesma forma?

    Exigir a ementa **na linha imediatamente seguinte** rejeitava decreto
    legítimo: entre o título e a ementa costuma entrar o nome do órgão —
    "Secretaria de Estado da Casa Civil" —, e o Decreto 48.313/2023 ficou de
    fora do acervo por isso. Procura-se a ementa nas primeiras linhas, não só
    na próxima.

    E a janela da fórmula precisa ser larga: decreto com muitos considerandos
    leva milhares de caracteres até chegar ao DECRETA.
    """
    janela = texto[fim_cabecalho : fim_cabecalho + 4000]
    if ABERTURA.search(janela):
        return True
    linhas = [l.strip() for l in janela.split(chr(10))[:8] if l.strip()]
    return any(parece_ementa(l) for l in linhas)


def pagina_em(texto: str, posicao: int) -> int:
    """A página é contada pelos avanços de forma que o pdftotext deixou."""
    return texto.count("\f", 0, posicao) + 1


def extrair_da_edicao(texto: str, data_edicao: str) -> list[dict]:
    candidatos = []
    for achado in CABECALHO.finditer(texto):
        numero = achado.group(1).replace(".", "")
        if not numero.isdigit() or int(numero) < MENOR_NUMERO_PLAUSIVEL:
            continue
        if not valida(texto, achado.start(), achado.end()):
            continue
        candidatos.append(achado)

    # Fronteiras: o próximo cabeçalho **válido**, ou o próximo ato de outra
    # espécie, o que vier antes.
    decretos = []
    for i, achado in enumerate(candidatos):
        limite = (
            candidatos[i + 1].start() if i + 1 < len(candidatos) else len(texto)
        )
        # A marca de fim da matéria manda; o começo de outro ato é reserva
        # para as edições em que ela falte.
        marca = fim_de_materia(texto, achado.end(), limite)
        if marca is not None:
            fim = marca
        else:
            outro = OUTRO_ATO.search(texto, achado.end(), limite)
            fim = outro.start() if outro else limite
        corpo = texto[achado.start() : fim].strip()

        mes = MESES.get(achado.group(3).upper())
        linhas = [l.strip() for l in corpo.split("\n")[1:] if l.strip()]
        ementa = ""
        for linha in linhas[:3]:
            if parece_ementa(linha):
                ementa = linha
                break

        decretos.append(
            {
                "numero": achado.group(1).replace(".", ""),
                "data": (
                    f"{int(achado.group(4)):04d}-{mes:02d}-{int(achado.group(2)):02d}"
                    if mes
                    else None
                ),
                "data_publicacao": data_edicao,
                "pagina": pagina_em(texto, achado.start()),
                "ementa": ementa or None,
                "texto": corpo,
                "chars": len(corpo),
            }
        )
    return decretos


def main() -> None:
    arquivos = sorted(DOERJ.glob("*.txt"))
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else len(arquivos)
    arquivos = arquivos[:limite]
    print(f"{len(arquivos)} edições")

    total = 0
    with SAIDA.open("w", encoding="utf-8") as f:
        for i, caminho in enumerate(arquivos, 1):
            texto = caminho.read_text(encoding="utf-8", errors="replace")
            for decreto in extrair_da_edicao(texto, caminho.stem):
                f.write(json.dumps(decreto, ensure_ascii=False) + "\n")
                total += 1
            if i % 500 == 0:
                print(f"  {i}/{len(arquivos)} — {total} decretos", flush=True)
    print(f"\n{total} decretos em {SAIDA}")


if __name__ == "__main__":
    main()
