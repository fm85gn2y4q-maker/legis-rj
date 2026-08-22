"""Acesso ao acervo da legislação estadual do Rio de Janeiro.

A REGRA QUE GOVERNA TODAS AS RESPOSTAS

A ferramenta prova o que encontrou, não o que existe. Nenhuma consulta a esta
base autoriza dizer "a norma está em vigor" — autoriza dizer o que a ALERJ
declarou e quando isso foi coletado.

A VIGÊNCIA TEM DOIS NÍVEIS, E ELES DISCORDAM

O cabeçalho traz a situação do **ato**. As revogações e as
inconstitucionalidades que interessam a uma peça estão por **dispositivo**,
soltas no corpo do texto, e não sobem para o cabeçalho. A Lei nº 4.024/2002
está marcada "Em Vigor" e tem dois parágrafos declarados inconstitucionais pelo
Órgão Especial em 2010. Responder pelo cabeçalho é acertar sobre o ato e errar
sobre o artigo — que é o que se cita.

E A SITUAÇÃO NEM SEMPRE EXISTE

    lei ordinária          declarada no documento
    lei complementar       declarada só na listagem, e falta em 28 de 234
    emenda constitucional  declarada só na listagem
    resolução              declarada no documento em 8.926 de 13.340
    decreto legislativo    NÃO EXISTE — a ALERJ não declara em lugar nenhum
    decreto do Executivo   NÃO EXISTE — vem do Diário, que não acompanha

Silêncio não é "em vigor": é ausência de informação, e a resposta tem de dizer
isso.

DUAS FONTES, E ELAS SABEM COISAS DIFERENTES

    ALERJ    declara situação e anota revogação por dispositivo
    DOERJ    publica o ato e segue; o texto é o do dia em que saiu

O decreto do Executivo só existe aqui pela segunda: a base da ALERJ que os
guardava parou no Decreto 42.200, de dezembro de 2009. Então sobre decreto o
acervo prova **publicação**, nunca vigência — e 345 números foram republicados,
o que significa que a primeira versão circulou com incorreção.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

ROTULOS = {
    "lei_ordinaria": "Lei Ordinária",
    "lei_complementar": "Lei Complementar",
    "emenda_constitucional": "Emenda Constitucional",
    "decreto_legislativo": "Decreto Legislativo",
    "resolucao": "Resolução",
    "decreto_executivo": "Decreto",
}

SEM_SITUACAO_NA_FONTE = {"decreto_legislativo", "decreto_executivo"}

# O que cada fonte é capaz de dizer — e não é a mesma coisa.
FONTES = {
    "ALERJ": "base CONTLEI da Assembleia Legislativa, que declara a situação do ato",
    "DOERJ": "Diário Oficial do Estado, que publica o ato e não acompanha o que "
    "acontece com ele depois",
}

# Como o usuário escreve, e o que isso quer dizer aqui.
APELIDOS = {
    "lei": "lei_ordinaria",
    "lei ordinaria": "lei_ordinaria",
    "lo": "lei_ordinaria",
    "lc": "lei_complementar",
    "lei complementar": "lei_complementar",
    "ec": "emenda_constitucional",
    "emenda": "emenda_constitucional",
    "emenda constitucional": "emenda_constitucional",
    "dl": "decreto_legislativo",
    "decreto legislativo": "decreto_legislativo",
    # "decreto", sem qualificar, é o do Governador — é o que se cita numa peça
    # administrativa. O decreto legislativo é ato interno da Assembleia e
    # precisa ser pedido pelo nome inteiro.
    "decreto": "decreto_executivo",
    "decreto estadual": "decreto_executivo",
    "decreto do executivo": "decreto_executivo",
    "resolucao": "resolucao",
    "resolução": "resolucao",
}


def normalizar_especie(bruto: str | None) -> str | None:
    if not bruto:
        return None
    chave = " ".join(bruto.strip().lower().split())
    if chave in ROTULOS:
        return chave
    return APELIDOS.get(chave)


@dataclass
class Ato:
    unid: str
    especie: str
    numero: str | None
    ano: str | None
    data: str | None
    situacao: str | None
    situacao_origem: str
    ementa: str | None
    autoria: str | None
    url: str
    avisos: list[str] = field(default_factory=list)
    numero_alternativo: str | None = None
    fonte: str = "ALERJ"
    publicado_em: str | None = None
    republicacoes: list[str] = field(default_factory=list)

    @property
    def citacao(self) -> str:
        """A referência que vai para a peça — com a ressalva dentro dela.

        Quando a ALERJ registra dois números para o mesmo ato, a citação não
        pode escolher um em silêncio: quem copiasse "Lei nº 79.428" citaria uma
        lei que não existe. A ressalva vai colada ao número, porque aviso em
        campo separado não sobrevive ao copiar e colar.
        """
        rotulo = ROTULOS.get(self.especie, self.especie)
        numero = self.numero or "?"
        if self.numero_alternativo:
            numero = f"{numero} [a fonte também registra {self.numero_alternativo}]"
        if self.data:
            ano, mes, dia = self.data.split("-")
            return f"{rotulo} nº {numero}, de {int(dia)}/{int(mes)}/{ano} (RJ)"
        return f"{rotulo} nº {numero}/{self.ano or '?'} (RJ)"


class Acervo:
    def __init__(self, banco: Path):
        self.caminho = Path(banco)
        self.con = sqlite3.connect(f"file:{self.caminho}?mode=ro", uri=True)
        self.con.row_factory = sqlite3.Row

    # ------------------------------------------------------------- cobertura

    def cobertura(self) -> dict:
        por_especie = {}
        for linha in self.con.execute(
            "SELECT especie, COUNT(*) n, "
            "SUM(situacao IS NOT NULL) com_situacao, MIN(ano) de, MAX(ano) ate "
            "FROM ato GROUP BY especie ORDER BY n DESC"
        ):
            por_especie[linha["especie"]] = {
                "rotulo": ROTULOS.get(linha["especie"], linha["especie"]),
                "atos": linha["n"],
                "com_situacao_declarada": linha["com_situacao"],
                "anos": f"{linha['de']}–{linha['ate']}",
                "vigencia_disponivel": linha["especie"] not in SEM_SITUACAO_NA_FONTE,
            }
        divergentes = self.con.execute(
            "SELECT SUM(data_divergente IS NOT NULL), SUM(numero_divergente IS NOT NULL) "
            "FROM ato"
        ).fetchone()
        por_fonte = {
            linha["fonte"]: linha["n"]
            for linha in self.con.execute(
                "SELECT fonte, COUNT(*) n FROM ato GROUP BY fonte"
            )
        }
        return {
            "fontes": {
                nome: {"atos": por_fonte.get(nome, 0), "o_que_declara": descricao}
                for nome, descricao in FONTES.items()
            },
            "por_especie": por_especie,
            "total": self.con.execute("SELECT COUNT(*) FROM ato").fetchone()[0],
            "atos_com_anotacao_de_dispositivo": self.con.execute(
                "SELECT COUNT(DISTINCT unid) FROM anotacao"
            ).fetchone()[0],
            "divergencias_da_fonte": {
                "data": divergentes[0],
                "numero": divergentes[1],
            },
            "republicacoes_de_decreto": self.con.execute(
                "SELECT COUNT(*) FROM ato WHERE republicacoes IS NOT NULL"
            ).fetchone()[0],
            "o_que_nao_esta_aqui": [
                "Vigência de decreto do Executivo: o Diário publica e segue, e a "
                "base da ALERJ que anotava vigência de decreto parou em 2009.",
                "Decreto anterior a 31/03/2008, quando começa o acervo do Diário.",
                "Legislação anterior a março de 1975, quando a Guanabara se "
                "fundiu ao antigo Estado do Rio.",
                "Revogação tácita, e norma federal superveniente.",
            ],
        }

    # --------------------------------------------------------------- buscas

    def pesquisar_ementa(
        self,
        consulta: str,
        especie: str | None = None,
        ano: str | None = None,
        situacao: str | None = None,
        limite: int = 20,
    ) -> list[Ato]:
        sql = (
            "SELECT a.* FROM busca_ementa b JOIN ato a ON a.rowid = b.rowid "
            "WHERE busca_ementa MATCH ?"
        )
        parametros: list = [consulta]
        if especie:
            sql += " AND a.especie = ?"
            parametros.append(especie)
        if ano:
            sql += " AND a.ano = ?"
            parametros.append(ano)
        if situacao:
            sql += " AND a.situacao = ?"
            parametros.append(situacao)
        sql += " ORDER BY rank LIMIT ?"
        parametros.append(limite)
        return [self._ato(linha) for linha in self.con.execute(sql, parametros)]

    def pesquisar_texto(
        self,
        consulta: str,
        especie: str | None = None,
        limite: int = 20,
    ) -> list[dict]:
        sql = (
            "SELECT a.*, snippet(busca_texto, 0, '«', '»', ' … ', 24) trecho "
            "FROM busca_texto b JOIN texto t ON t.rowid = b.rowid "
            "JOIN ato a ON a.unid = t.unid WHERE busca_texto MATCH ?"
        )
        parametros: list = [consulta]
        if especie:
            sql += " AND a.especie = ?"
            parametros.append(especie)
        sql += " ORDER BY rank LIMIT ?"
        parametros.append(limite)
        saida = []
        for linha in self.con.execute(sql, parametros):
            ato = self._ato(linha)
            saida.append({"ato": ato, "trecho": linha["trecho"]})
        return saida

    # ----------------------------------------------------------------- ato

    def obter(self, especie: str, numero: str, ano: str | None = None) -> list[Ato]:
        digitos = "".join(c for c in numero if c.isdigit())
        alvo = int(digitos) if digitos else -1
        sql = "SELECT * FROM ato WHERE especie = ? AND numero_ordenavel = ?"
        parametros: list = [especie, alvo]
        if ano:
            sql += " AND ano = ?"
            parametros.append(ano)
        achados = [self._ato(l) for l in self.con.execute(sql, parametros)]
        if achados:
            return achados
        # Procurar pelo número que o texto do ato declara: a Lei 9.428/2021
        # está guardada sob 79428 porque a ALERJ digitou um dígito a mais, e
        # quem a procura pelo número certo não a encontraria.
        sql = (
            "SELECT * FROM ato WHERE especie = ? AND numero_divergente IS NOT NULL "
            "AND json_extract(numero_divergente, '$.texto_do_ato') = ?"
        )
        parametros = [especie, digitos]
        if ano:
            sql += " AND ano = ?"
            parametros.append(ano)
        try:
            return [self._ato(l) for l in self.con.execute(sql, parametros)]
        except sqlite3.OperationalError:  # SQLite sem json1
            return []

    def texto(self, unid: str) -> str:
        linha = self.con.execute(
            "SELECT texto FROM texto WHERE unid = ?", (unid,)
        ).fetchone()
        return linha["texto"] if linha else ""

    def anotacoes(self, unid: str) -> dict[str, list[str]]:
        saida: dict[str, list[str]] = {}
        for linha in self.con.execute(
            "SELECT tipo, trecho FROM anotacao WHERE unid = ?", (unid,)
        ):
            saida.setdefault(linha["tipo"], []).append(linha["trecho"])
        return saida

    # ------------------------------------------------------------ vigência

    def vigencia(self, ato: Ato) -> dict:
        """O que a fonte declara — nos dois níveis, e sem completar lacuna."""
        anotacoes = self.anotacoes(ato.unid)
        declarado = {
            "ato": {
                "situacao_declarada": ato.situacao,
                "origem": ato.situacao_origem,
            },
            "dispositivos": {
                tipo: trechos for tipo, trechos in anotacoes.items()
            },
        }
        avisos: list[str] = []
        if ato.fonte == "DOERJ":
            avisos.append(
                "Este decreto veio do Diário Oficial, que publica o ato e segue: "
                "não há situação declarada, e o texto é o do dia da publicação. "
                "Revogação posterior só aparece se outro decreto a disser — a "
                "base da ALERJ, que anota vigência, não cobre decreto do "
                "Executivo depois de 2009."
            )
        elif ato.especie in SEM_SITUACAO_NA_FONTE:
            avisos.append(
                f"A ALERJ não declara situação para {ROTULOS[ato.especie]}: "
                "a ausência aqui não é sinal de que a norma esteja em vigor."
            )
        elif not ato.situacao:
            avisos.append(
                "Este ato não traz situação declarada, nem no documento nem na "
                "listagem — não é o mesmo que estar em vigor."
            )
        if anotacoes:
            avisos.append(
                "Há anotação por dispositivo neste ato. A situação do cabeçalho "
                "vale para o ato inteiro e NÃO alcança o artigo anotado: "
                "confira o dispositivo que pretende citar."
            )
        avisos.append(
            "Não constam desta base: revogação tácita, norma federal ou estadual "
            "superveniente, e declaração de inconstitucionalidade que a ALERJ "
            "não tenha anotado."
        )
        return {"citacao": ato.citacao, "declarado": declarado, "avisos": avisos}

    # ---------------------------------------------------------------- apoio

    def _ato(self, linha: sqlite3.Row) -> Ato:
        avisos = []
        alternativo = None
        if linha["numero_divergente"]:
            d = json.loads(linha["numero_divergente"])
            alternativo = d["texto_do_ato"]
            avisos.append(
                f"A ALERJ registra o número {d['cabecalho']} no cabeçalho e "
                f"{d['texto_do_ato']} no texto do próprio ato."
            )
        if linha["data_divergente"]:
            d = json.loads(linha["data_divergente"])
            avisos.append(
                f"Data divergente na fonte: {d['cabecalho']} no campo e "
                f"{d['abertura']} no texto do ato."
            )
        if linha["ano_inferido"]:
            avisos.append(
                "O ano estava com dois dígitos na fonte; o século foi inferido."
            )
        campos = linha.keys()
        fonte = linha["fonte"] if "fonte" in campos else "ALERJ"
        republicacoes = []
        if "republicacoes" in campos and linha["republicacoes"]:
            republicacoes = json.loads(linha["republicacoes"])
            avisos.append(
                f"Este decreto foi publicado mais de uma vez: {', '.join(republicacoes)} "
                f"e {linha['publicado_em']}. Vale a última — a versão anterior "
                "circulou com incorreção."
            )
        if "truncado" in campos and linha["truncado"]:
            avisos.append(
                "O texto deste ato saiu curto demais na extração do Diário: "
                "provavelmente falta o corpo. Confira no inteiro teor."
            )
        return Ato(
            unid=linha["unid"],
            especie=linha["especie"],
            numero=linha["numero"],
            ano=linha["ano"],
            data=linha["data"],
            situacao=linha["situacao"],
            situacao_origem=linha["situacao_origem"],
            ementa=linha["ementa"],
            autoria=linha["autoria"],
            url=linha["url"],
            avisos=avisos,
            numero_alternativo=alternativo,
            fonte=fonte,
            publicado_em=linha["publicado_em"] if "publicado_em" in campos else None,
            republicacoes=republicacoes,
        )


RE_REFERENCIA = re.compile(
    # A ordem manda: a alternativa mais longa vem primeiro, ou "decreto
    # legislativo" casaria só o "decreto" e viraria decreto do Executivo.
    r"(?P<especie>lei\s+complementar|emenda\s+constitucional|decreto\s+legislativo|"
    r"decreto\s+estadual|decreto\s+do\s+executivo|resolu[çc][ãa]o|decreto|lei|lc|ec|dl)\s*"
    r"(?:n[ºo°.]?\s*)?(?P<numero>[\d.]+)\s*(?:/\s*(?P<ano>\d{2,4}))?",
    re.IGNORECASE,
)


def interpretar_referencia(texto: str) -> dict | None:
    """"lei 5427/2009", "LC 232", "EC nº 99" — o que o advogado digita."""
    achado = RE_REFERENCIA.search(texto or "")
    if not achado:
        return None
    ano = achado.group("ano")
    if ano and len(ano) == 2:
        ano = f"19{ano}" if int(ano) >= 75 else f"20{ano}"
    return {
        "especie": normalizar_especie(achado.group("especie")),
        "numero": achado.group("numero").replace(".", ""),
        "ano": ano,
    }
