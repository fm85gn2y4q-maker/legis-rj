"""Extrai de cada documento da ALERJ o que vira registro do acervo.

O ACHATAMENTO DO HTML É A PARTE QUE ERRA CALADO

O link da busca manda o Domino **grifar o termo procurado dentro do
documento**. Um ato achado pela consulta "1" volta com todo `1` embrulhado:

    <font color='green'><b>1</b></font>981

Trocar tag por espaço, que é o reflexo de todo mundo, transforma isso em
`1 981` — e aí a lei de 1981 fica sem ano, o número 5312 vira "5 312", e a
data `12/03/1981` vira `1 2/03/ 1 981`. Medido antes do conserto: **39% dos
documentos** ficavam sem número e ano identificáveis, e nada no resultado
denunciava o motivo.

A correção é distinguir tag que separa palavra de tag que não separa. `<font>`,
`<b>` e `<a>` são maquiagem no meio da palavra e saem sem deixar espaço;
`<td>`, `<p>` e `<br>` separam de verdade.

O QUE SE EXTRAI, E DE ONDE

O cabeçalho é uma tabela de rótulo e valor — `Lei nº`, `Data da Lei`,
`Texto da Lei [ Em Vigor ]`. O rótulo muda com a espécie (`Data do Decreto`,
`Texto da Resolução`), então casa-se pelo padrão, não pela palavra exata.

A data vem em **MM/DD/AAAA**, locale do Domino: `07/01/1981` é 1º de julho, não
7 de janeiro. Ler como brasileiro inverte todo dia menor ou igual a 12 e não dá
erro nenhum.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

# Tags que não separam palavra: some com elas antes de qualquer coisa.
MAQUIAGEM = ("font", "b", "i", "u", "em", "strong", "span", "a", "sup", "sub")

MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}

# O sufixo de letra não é enfeite: a Lei nº 2.803-A/1997 é outra lei que a
# 2.803/1997, e exigir só dígitos deixava as duas de fora do acervo.
RE_NUMERO = re.compile(
    r"(?:Lei|Lei Complementar|Emenda|Decreto|Resolu[çc][ãa]o)\s*n[ºo°]\s*"
    r"(\d[\d.]*(?:-[A-Za-z])?)\s*/\s*(\d{4})",
    re.IGNORECASE,
)
RE_DATA = re.compile(r"Data d[aeo]\s+\w+\s*(\d{1,2})/(\d{1,2})/(\d{4})", re.IGNORECASE)
RE_SITUACAO = re.compile(r"Texto d[aeo]\s+\w+\s*\[\s*([^\]]{2,45}?)\s*\]", re.IGNORECASE)
# "LEI Nº 8.976 DE 17 DE AGOSTO DE 2020." — a linha de abertura do ato.
#
# Duas armadilhas aqui, e as duas já morderam:
#
# 1. `[\d.]+` casa um ponto sozinho. Tirados os pontos, o número virava string
#    vazia, e o ato aparecia como divergente de si mesmo. Exige-se dígito.
# 2. **Abertura e citação têm a mesma forma.** "ALTERA A LEI Nº 2.592 DE 1996"
#    é indistinguível da abertura de um ato, e vem antes dela em toda lei que
#    altera outra. Pegar a primeira ocorrência atribuiu o número 2.592 a um ato
#    que é o 7.177 — em 87 de 1.500 documentos. Por isso não se pega a
#    primeira: pega-se a que **bate com o número do cabeçalho**, e não havendo,
#    diz-se que não houve.
RE_ABERTURA = re.compile(
    r"(LEI COMPLEMENTAR|LEI|DECRETO LEGISLATIVO|DECRETO|EMENDA CONSTITUCIONAL|"
    r"RESOLU[ÇC][ÃA]O)\s*N?[ºo°]?\s*(\d[\d.]*(?:-[A-Za-z])?)[^\n]{0,40}?"
    r"DE\s+(\d{1,2})[ºo°]?\s+DE\s+"
    r"([A-ZÇÃÉÊÍÓÔÕÚa-zçãéêíóôõú]+)\s+DE\s+(\d{4})"
)

ANOTACOES = {
    "revogacao_expressa": re.compile(
        r"[Rr]evogad[oa]s?\s+pel[ao]\s+([^.\n]{0,90})"
    ),
    "nova_redacao": re.compile(
        r"[Nn]ova\s+reda[çc][ãa]o\s+dada\s+pel[ao]\s+([^.\n]{0,90})"
    ),
    "inconstitucionalidade": re.compile(
        r"([^.\n]{0,120}inconstitucional[^.\n]{0,120})"
    ),
}


def achatar(html: str) -> str:
    """HTML em texto, sem inventar espaço onde não havia."""
    sopa = BeautifulSoup(html, "html.parser")
    for tag in sopa(["script", "style"]):
        tag.decompose()
    for tag in sopa.find_all(MAQUIAGEM):
        tag.unwrap()  # tira a tag, mantém o texto colado
    for tag in sopa.find_all(["br", "p", "tr", "td", "div", "table"]):
        tag.insert_after("\n")
    texto = sopa.get_text()
    texto = re.sub(r"[ \t\xa0]+", " ", texto)
    return re.sub(r"\n\s*\n+", "\n", texto).strip()


def data_iso(mes: str, dia: str, ano: str) -> str:
    """O Domino escreve MM/DD/AAAA. Ver o cabeçalho do módulo."""
    return f"{int(ano):04d}-{int(mes):02d}-{int(dia):02d}"


def extrair(html: str, unid: str = "") -> dict:
    texto = achatar(html)
    cabecalho = texto[:1200]

    especie = ""
    sopa = BeautifulSoup(html, "html.parser")
    if sopa.title and sopa.title.string:
        especie = sopa.title.string.strip()

    registro: dict = {"unid": unid, "especie": especie, "chars": len(texto)}

    numero = RE_NUMERO.search(cabecalho)
    if numero:
        registro["numero"] = numero.group(1).replace(".", "")
        registro["ano"] = numero.group(2)

    data = RE_DATA.search(cabecalho)
    if data:
        registro["data"] = data_iso(data.group(1), data.group(2), data.group(3))

    situacao = RE_SITUACAO.search(cabecalho)
    if situacao:
        registro["situacao"] = situacao.group(1)

    # A abertura serve de conferência do cabeçalho, não de fonte alternativa:
    # só vale a ocorrência cujo número é o mesmo do cabeçalho.
    for achado in RE_ABERTURA.finditer(texto[:4000]):
        if achado.group(2).replace(".", "") != registro.get("numero"):
            continue
        mes = MESES.get(achado.group(4).lower())
        registro["abertura"] = {
            "especie_no_texto": achado.group(1),
            "numero": achado.group(2).replace(".", ""),
            "data": (
                f"{int(achado.group(5)):04d}-{mes:02d}-{int(achado.group(3)):02d}"
                if mes
                else None
            ),
        }
        break

    # A ALERJ registra a data duas vezes: no campo do cabeçalho e por extenso
    # na abertura do ato. Medido: em 3% dos documentos as duas discordam — o
    # campo diz 01/08/0007 e o texto diz 8 de janeiro de 2007; o campo diz 20
    # de abril e o texto diz 27. É divergência **da fonte**, não da extração.
    #
    # Não se escolhe uma: guarda-se as duas e marca-se. Quem responde com uma
    # data sem dizer que a outra existe está inventando certeza que a ALERJ
    # não tem. Confrontar com o Diário Oficial resolve caso a caso, e o acervo
    # do DOERJ já está aqui para isso.
    abertura = registro.get("abertura")
    if abertura and abertura.get("data") and registro.get("data"):
        if abertura["data"] != registro["data"]:
            registro["data_divergente"] = {
                "cabecalho": registro["data"],
                "abertura": abertura["data"],
            }

    marcas: dict[str, list[str]] = {}
    for nome, padrao in ANOTACOES.items():
        achados = [" ".join(m.group(1).split()) for m in padrao.finditer(texto)]
        if achados:
            marcas[nome] = achados[:20]
    if marcas:
        registro["anotacoes"] = marcas

    registro["texto"] = texto
    return registro
