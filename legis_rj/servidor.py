"""Servidor MCP da legislação estadual do Rio de Janeiro.

Fala os dois transportes porque os clientes divergem: o Claude conversa por
stdio com um processo local, e o ChatGPT só aceita servidor remoto por HTTP.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .acervo import ROTULOS, Acervo, interpretar_referencia, normalizar_especie

BANCO = Path(
    os.environ.get(
        "LEGIS_RJ_BANCO",
        Path(__file__).resolve().parent.parent / "dados" / "legis-rj.sqlite",
    )
)

mcp = FastMCP("legis-rj")
_acervo: Acervo | None = None


def acervo() -> Acervo:
    global _acervo
    if _acervo is None:
        _acervo = Acervo(BANCO)
    return _acervo


def _resumo(ato) -> dict[str, Any]:
    saida = {
        "citacao": ato.citacao,
        "especie": ROTULOS.get(ato.especie, ato.especie),
        "numero": ato.numero,
        "ano": ato.ano,
        "data": ato.data,
        "situacao_declarada": ato.situacao,
        "origem_da_situacao": ato.situacao_origem,
        "ementa": ato.ementa,
        "autoria": ato.autoria,
        "url": ato.url,
        "id": ato.unid,
    }
    if ato.avisos:
        saida["avisos"] = ato.avisos
    return saida


@mcp.tool()
def cobertura_do_acervo() -> dict:
    """O que este acervo tem, e principalmente o que ele NÃO tem.

    Chame antes de afirmar que uma norma não existe: a ausência aqui pode ser
    ausência da coleta, não da legislação.
    """
    return acervo().cobertura()


@mcp.tool()
def pesquisar_legislacao(
    consulta: str,
    especie: str | None = None,
    ano: str | None = None,
    situacao: str | None = None,
    limite: int = 20,
) -> dict:
    """Pesquisa na **ementa** — o resumo oficial do que o ato dispõe.

    É a busca certa para "que leis tratam de saneamento": devolve as leis
    *sobre* o tema. Para achar toda menção a uma palavra dentro do texto,
    use `pesquisar_inteiro_teor`.

    `especie` aceita: lei, lei complementar, emenda constitucional, decreto
    legislativo, resolução.
    """
    esp = normalizar_especie(especie)
    achados = acervo().pesquisar_ementa(consulta, esp, ano, situacao, limite)
    return {
        "consulta": consulta,
        "encontrados": len(achados),
        "atos": [_resumo(a) for a in achados],
    }


@mcp.tool()
def pesquisar_inteiro_teor(
    consulta: str, especie: str | None = None, limite: int = 20
) -> dict:
    """Pesquisa dentro do **texto integral**, e devolve o trecho que casou.

    Serve para achar o dispositivo que trata de algo, ou toda norma que cite
    outra. Traz mais ruído que a busca por ementa, e é isso que se quer aqui.
    """
    esp = normalizar_especie(especie)
    achados = acervo().pesquisar_texto(consulta, esp, limite)
    return {
        "consulta": consulta,
        "encontrados": len(achados),
        "trechos": [
            {"ato": _resumo(x["ato"]), "trecho": x["trecho"]} for x in achados
        ],
    }


@mcp.tool()
def obter_ato(
    referencia: str | None = None,
    especie: str | None = None,
    numero: str | None = None,
    ano: str | None = None,
    com_texto: bool = True,
) -> dict:
    """Traz um ato pelo número — por referência escrita ou pelos campos.

    `referencia` entende o que se digita numa peça: "lei 5427/2009",
    "LC 232", "EC nº 99". Sem ela, informe `especie` e `numero`.
    """
    esp = normalizar_especie(especie)
    if referencia:
        lido = interpretar_referencia(referencia)
        if lido:
            esp = esp or lido["especie"]
            numero = numero or lido["numero"]
            ano = ano or lido["ano"]
    if not (esp and numero):
        return {
            "erro": "informe a espécie e o número — por exemplo, "
            "referencia='lei 5427/2009'"
        }

    achados = acervo().obter(esp, numero, ano)
    if not achados:
        return {
            "encontrados": 0,
            "aviso": "Não localizei este ato no acervo. Isso não prova que ele "
            "não exista: veja `cobertura_do_acervo` para o alcance da base.",
        }
    saida = []
    for ato in achados:
        registro = _resumo(ato)
        registro["vigencia"] = acervo().vigencia(ato)
        if com_texto:
            registro["texto"] = acervo().texto(ato.unid)
        saida.append(registro)
    return {"encontrados": len(saida), "atos": saida}


@mcp.tool()
def verificar_vigencia(
    referencia: str | None = None,
    especie: str | None = None,
    numero: str | None = None,
    ano: str | None = None,
) -> dict:
    """O que a ALERJ declara sobre a vigência — **nos dois níveis**.

    Chame antes de apresentar qualquer norma como fundamento.

    Devolve a situação do ato E as anotações por dispositivo, que são coisas
    diferentes: um ato "Em Vigor" pode ter artigos revogados ou declarados
    inconstitucionais, e a marca disso não sobe para o cabeçalho.

    O que esta ferramenta NÃO devolve, em nenhuma hipótese: que a norma esteja
    em vigor. Devolve o que a fonte declarou. Ficam de fora a revogação tácita,
    a norma superveniente e a inconstitucionalidade que a ALERJ não anotou.
    """
    resposta = obter_ato(referencia, especie, numero, ano, com_texto=False)
    if not resposta.get("atos"):
        return resposta
    return {
        "encontrados": resposta["encontrados"],
        "vigencia": [
            {**a["vigencia"], "url": a["url"], "ementa": a["ementa"]}
            for a in resposta["atos"]
        ],
    }


@mcp.tool()
def ler_ato(id: str, de: int = 0, ate: int = 20000) -> dict:
    """Lê um trecho do texto integral pelo identificador, para atos longos."""
    texto = acervo().texto(id)
    if not texto:
        return {"erro": "identificador não encontrado"}
    return {
        "id": id,
        "chars": len(texto),
        "trecho": texto[de:ate],
        "continua": ate < len(texto),
    }


def main() -> None:
    transporte = os.environ.get("LEGIS_RJ_TRANSPORTE", "stdio")
    if transporte == "http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
