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
from datetime import date

import ler_texto
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DOERJ = RAIZ / "dados" / "doerj"
SAIDA = DOERJ / "decretos.jsonl"

MESES = {
    "JANEIRO": 1, "FEVEREIRO": 2, "MARCO": 3, "MARÇO": 3, "ABRIL": 4,
    "MAIO": 5, "JUNHO": 6, "JULHO": 7, "AGOSTO": 8, "SETEMBRO": 9,
    "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12,
}

# TRÊS VARIAÇÕES DE TIPOGRAFIA QUE CUSTARAM O RESÍDUO INTEIRO
#
# O cabeçalho não é digitado duas vezes igual. Medido nos cadernos que a
# recuperação já tinha em disco:
#
#     DECRETO Nº 42.457 DE 10. DE MAIO DE 2010      ponto depois do dia
#     DECRETO N º 42.337 DE 08 DE MARÇO DE 2010     espaço entre N e º
#     DECRETO Nº 42.472 DE 25.. DE MAIO DE 2010     dois pontos
#
# A regex exigia `Nº` colado e não admitia ponto após o dia. Os três decretos
# estavam publicados, localizados e baixados — e o extrator passava por cima
# dos três, devolvendo "edição sem decreto". Foi por isso que o resíduo de 412
# rendeu zero em duas rodadas de rede: o problema nunca esteve na localização.
# A GRAMÁTICA DO CABEÇALHO, LEVANTADA DOS PRÓPRIOS CADERNOS
#
# O cabeçalho não é digitado duas vezes igual, e remendar variante por variante
# foi perda de tempo: cada correção revelava a seguinte. Levantei a gramática
# medindo 260 cadernos — o que separa "DECRETO" do número, e o número do ano:
#
#     entre DECRETO e o número      entre o número e o ano
#     ------------------------      ----------------------------------
#     Nº            1.126           DE d DE MES DE          745
#     N.º              17           , DE d DE MES DE        148
#     ESTADUAL Nº      12           DE d/d/                  27
#     N º               5           , DE d/d/                21
#     (nada)            5           DE d.d.                  16
#                                   , DE d.d.                16
#                                   DE d. DE MES DE          10
#                                   DE d.. DE MES.. DE        5
#
# Duas lições. A pontuação é ruído de diagramação e pode aparecer em qualquer
# junta — por isso as juntas viram `[.\s]*`. E a data também sai em forma
# NUMÉRICA (`DE 30/04/2010`, `DE 30.04.2010`), que a regex antiga não cobria de
# jeito nenhum: eram 80 ocorrências só nesses 260 cadernos.
#
# O que NÃO entra: `42.434/2010` (164 ocorrências) é citação, não cabeçalho —
# e fica de fora porque a gramática exige `DE` antes da data.
_JUNTA = r"[.\s]*"
# `n` minúsculo aparece: "DECRETO n° 42.910 DE 01 DE ABRIL DE 2011". Abrir só
# essa letra é seguro — `DECRETO` continua exigido em CAIXA ALTA, e é a caixa
# alta que separa o cabeçalho da citação em texto corrido ("o Decreto nº ...").
_ABERTURA = r"DECRETO\s+(?:ESTADUAL\s+)?(?:[Nn]" + _JUNTA + r"[ºO°o]?)?" + _JUNTA
_NUMERO = r"(?P<num>\d{2}[.\s]?\d{3})"
_DATA = (
    r"(?:"
    r"(?P<dia>\d{1,2})" + _JUNTA + r"DE" + _JUNTA
    + r"(?P<mes_nome>[A-ZÇÃÉÊÍÓÔÕÚ]{4,})" + _JUNTA
    + r"(?:DE" + _JUNTA + r")?(?P<ano>\d{4})"
    r"|"
    r"(?P<dia_n>\d{1,2})[./](?P<mes_n>\d{1,2})[./](?P<ano_n>\d{4})"
    r")"
)
_CABECALHO = _ABERTURA + _NUMERO + r"[,\s]*DE" + _JUNTA + _DATA

CABECALHO = re.compile(r"^" + _CABECALHO, re.MULTILINE)

# O MESMO CABEÇALHO SEM A ÂNCORA DE LINHA — E POR QUE ELE PRECISA EXISTIR
#
# Em parte das edições o ato não começa a linha: vem emendado no fio do texto,
# depois do título da seção e às vezes com asterisco de republicação —
#
#     ... circulam hoje em um só caderno  ATOS DO PODER EXECUTIVO *DECRETO Nº
#     45.739 DE 23 DE AGOSTO DE 2016  ABRE CRÉDITO SUPLEMENTAR ...
#
# Ancorado em `^`, o extrator não via esse decreto e devolvia zero para a
# edição inteira. Foi assim que 505 decretos passaram por ausentes enquanto
# estavam publicados e em disco.
#
# Soltar a âncora, porém, faz entrar a CITAÇÃO: "nos termos do Decreto nº
# 14.870..." casa igual. A defesa é a data que o próprio cabeçalho carrega.
# Medido em 120 cadernos: os cabeçalhos legítimos ficam a 1..177 dias da
# edição (mediana 1, p95 5); as citações saltam para 1.053, 2.337, 2.410 e
# 8.893 dias. Não há nada no meio — o corte separa sem ambiguidade.
CABECALHO_SOLTO = re.compile(r"\*?" + _CABECALHO)
DIAS_ATE_A_PUBLICACAO = 365   # folga larga: o maior legítimo medido foi 177
DIAS_ANTES_DA_EDICAO = 3      # o ato pode sair datado de dias à frente

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


# Decreto de OUTRA autoridade, citado dentro de um ato estadual. O acervo é da
# legislação do **Estado**; o decreto do Município do Rio tem numeração própria
# e muito mais alta, e um só deles entrando aqui não é um erro pequeno: o
# 53.879/2024 do Prefeito subiu o teto da série de 50.431 para 53.879 e a
# lacuna declarada saltou de 4,9% para 32,1% — três mil e quinhentos decretos
# fantasma, todos inventados por um registro.
#
# Escapa da validação porque a fórmula do ato estadual vem logo depois:
#
#     DECRETO Nº 53.879, DE 14 DE JANEIRO DE 2024, DO PREFEITO MUNICIPAL DO
#     RIO DE JANEIRO/RJ. O GOVERNADOR DO ESTADO DO RIO DE JANEIRO, no uso...
#
# O que denuncia é o qualificador colado no cabeçalho.
DE_OUTRA_AUTORIDADE = re.compile(
    r"^[,\s.]*(?:D[OAE]\s+)?(?:PREFEIT[OA]|MUNIC[ÍI]PIO|PREFEITURA|"
    r"C[ÂA]MARA\s+MUNICIPAL|GOVERNO\s+FEDERAL|PRESID[ÊE]NCIA)",
    re.IGNORECASE,
)


# REFERÊNCIA AO ATO, NÃO O ATO — A FORMA "QUE"
#
# O anexo de execução orçamentária abre citando o decreto que o autoriza, e a
# citação tem a mesma forma do cabeçalho:
#
#     DECRETO Nº 47.189, DE 29 DE JULHO DE 2020, QUE ALTERA A ESTRUTURA
#     ORGANIZACIONAL DA SECRETARIA... UO: 21322 Instituto de Segurança...
#
# O que denuncia é o `QUE` logo depois da data: o cabeçalho verdadeiro emenda
# direto na ementa, sem conectivo — "DECRETO Nº 49.643 DE 23 DE MAIO DE 2025.
# APROVA O REGULAMENTO...". E o `UO:` que vem em seguida é unidade
# orçamentária, coisa de anexo, não de decreto.
#
# O estrago era grande: o montador guarda a ÚLTIMA publicação de cada número,
# então o Decreto 49.135 estava no banco com o blob de 144.499 caracteres do
# anexo de 2025 no lugar do ato de 16.689 publicado em 2024.
REFERENCIA_A_ATO = re.compile(r"^[,\s.]*QUE\s+[A-ZÇÃÉÊÍÓÔÕÚ]", re.IGNORECASE)
UNIDADE_ORCAMENTARIA = re.compile(r"UO\s*:\s*\d")

# Acima disto, aceitar o cabeçalho só porque a linha seguinte "parece ementa"
# não basta. Um ato de 100 mil caracteres tem fórmula de promulgação; se ela
# não aparece, o que se capturou foi um índice que começa parecido.
CORPO_EXIGE_FORMULA = 100_000


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
    return bool(caminho_da_validacao(texto, fim_cabecalho))


def caminho_da_validacao(texto: str, fim_cabecalho: int) -> str | None:
    """Não só se vale, mas **por qual prova** — e a prova tem forças diferentes.

    `formula` é a promulgação do próprio ato ("O GOVERNADOR DO ESTADO",
    "DECRETA"): prova forte, o texto capturado é o decreto. `ementa` é apenas
    uma linha em caixa alta logo abaixo do título: prova fraca, que existe
    porque 7% dos decretos legítimos não trazem a fórmula na janela — e é por
    ela que entrava índice de anexo com cara de ato.
    """
    janela = texto[fim_cabecalho : fim_cabecalho + 4000]
    if DE_OUTRA_AUTORIDADE.match(janela):
        return None
    if REFERENCIA_A_ATO.match(janela):
        return None
    if UNIDADE_ORCAMENTARIA.search(janela[:300]):
        return None
    if ABERTURA.search(janela):
        return "formula"
    linhas = [l.strip() for l in janela.split(chr(10))[:8] if l.strip()]
    return "ementa" if any(parece_ementa(l) for l in linhas) else None


def pagina_em(texto: str, posicao: int) -> int:
    """A página é contada pelos avanços de forma que o pdftotext deixou."""
    return texto.count("\f", 0, posicao) + 1


def numero_do(achado) -> str:
    return achado.group("num").replace(".", "").replace(" ", "")


def dia_do(achado) -> int:
    return int(achado.group("dia") or achado.group("dia_n"))


def ano_do(achado) -> int:
    return int(achado.group("ano") or achado.group("ano_n"))


def mes_do(achado):
    """O mês vem por extenso ou em algarismo, conforme a edição."""
    if achado.group("mes_nome"):
        return MESES.get(achado.group("mes_nome").upper())
    numerico = int(achado.group("mes_n"))
    return numerico if 1 <= numerico <= 12 else None


def data_do_cabecalho(achado) -> "date | None":
    mes = mes_do(achado)
    if not mes:
        return None
    try:
        return date(ano_do(achado), mes, dia_do(achado))
    except ValueError:
        return None


def perto_da_edicao(achado, data_edicao: str) -> bool:
    """O ato datado longe da edição não é publicação: é citação."""
    propria = data_do_cabecalho(achado)
    if propria is None:
        return False
    try:
        edicao = date.fromisoformat(data_edicao)
    except ValueError:
        return True   # sem data de edição não há como duvidar
    return -DIAS_ANTES_DA_EDICAO <= (edicao - propria).days <= DIAS_ATE_A_PUBLICACAO


def extrair_da_edicao(texto: str, data_edicao: str) -> list[dict]:
    candidatos = []
    vistos = set()
    prova: dict[int, str] = {}
    for achado in CABECALHO.finditer(texto):
        numero = numero_do(achado)
        if not numero.isdigit() or int(numero) < MENOR_NUMERO_PLAUSIVEL:
            continue
        via = caminho_da_validacao(texto, achado.end())
        if not via:
            continue
        candidatos.append(achado)
        prova[achado.start()] = via
        vistos.add(achado.start())

    # Segunda passada, só para o que a âncora de linha não alcança. A guarda de
    # data é o que impede a citação de entrar como ato — e ela vale apenas
    # aqui: o que já vinha pela âncora continua entrando como antes, para a
    # correção não mudar por baixo o acervo que já foi conferido.
    for achado in CABECALHO_SOLTO.finditer(texto):
        if achado.start() in vistos or any(
            c.start() <= achado.start() < c.end() for c in candidatos
        ):
            continue
        numero = numero_do(achado)
        if not numero.isdigit() or int(numero) < MENOR_NUMERO_PLAUSIVEL:
            continue
        if not perto_da_edicao(achado, data_edicao):
            continue
        via = caminho_da_validacao(texto, achado.end())
        if not via:
            continue
        candidatos.append(achado)
        prova[achado.start()] = via
        vistos.add(achado.start())

    candidatos.sort(key=lambda m: m.start())

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
            fim, fronteira = marca, "marca"
        else:
            outro = OUTRO_ATO.search(texto, achado.end(), limite)
            fim = outro.start() if outro else limite
            fronteira = "outro_ato" if outro else "limite"
        corpo = texto[achado.start() : fim].strip()
        # Prova fraca não sustenta corpo gigante. O ato de verdade com esse
        # tamanho traz a fórmula de promulgação; sem ela, o que se capturou
        # começa como decreto e segue como outra coisa.
        if len(corpo) > CORPO_EXIGE_FORMULA and prova.get(achado.start()) != "formula":
            continue

        mes = mes_do(achado)
        linhas = [l.strip() for l in corpo.split("\n")[1:] if l.strip()]
        ementa = ""
        for linha in linhas[:3]:
            if parece_ementa(linha):
                ementa = linha
                break

        decretos.append(
            {
                "numero": numero_do(achado),
                "data": (
                    f"{ano_do(achado):04d}-{mes:02d}-{dia_do(achado):02d}"
                    if mes
                    else None
                ),
                "data_publicacao": data_edicao,
                "pagina": pagina_em(texto, achado.start()),
                "ementa": ementa or None,
                "texto": corpo,
                "chars": len(corpo),
                # Como o fim do ato foi decidido: `marca` é o `Id:` que o
                # próprio Diário imprime, `outro_ato` é o ato seguinte, e
                # `limite` é não ter achado nenhum dos dois — nesse caso o
                # corpo foi até onde deu, e o tamanho não prova nada.
                "fronteira": fronteira,
            }
        )
    return decretos


def main() -> None:
    arquivos = ler_texto.edicoes(DOERJ)
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else len(arquivos)
    arquivos = arquivos[:limite]
    print(f"{len(arquivos)} edições")

    total = 0
    # Grava num arquivo à parte e só troca no fim, como o banco: abrir a
    # saída em "w" apaga a extração boa no primeiro byte, e se a rodada
    # morrer no meio — o disco deste acervo já derrubou processo — o que
    # sobra é meia extração com cara de inteira.
    parcial = SAIDA.with_suffix(".jsonl.parcial")
    with parcial.open("w", encoding="utf-8") as f:
        for i, caminho in enumerate(arquivos, 1):
            texto = ler_texto.ler(caminho)
            for decreto in extrair_da_edicao(texto, ler_texto.dia_de(caminho)):
                f.write(json.dumps(decreto, ensure_ascii=False) + "\n")
                total += 1
            if i % 500 == 0:
                print(f"  {i}/{len(arquivos)} — {total} decretos", flush=True)
    if SAIDA.exists():
        SAIDA.unlink()
    parcial.rename(SAIDA)
    print(f"\n{total} decretos em {SAIDA}")


if __name__ == "__main__":
    main()
