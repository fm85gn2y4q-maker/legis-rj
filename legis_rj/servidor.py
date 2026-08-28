"""Servidor MCP da legislação estadual do Rio de Janeiro.

Fala os dois transportes porque os clientes divergem: o Claude conversa por
stdio com um processo local, e o ChatGPT só aceita servidor remoto por HTTP.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .acervo import ROTULOS, Acervo, interpretar_referencia, normalizar_especie

_LOCAIS = ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"]


def _caminho_padrao() -> Path:
    return Path(
        os.environ.get(
            "LEGIS_RJ_BANCO",
            Path(__file__).resolve().parent.parent / "banco" / "legis-rj.sqlite",
        )
    )


def seguranca_de_transporte(dominios: list[str] | None) -> TransportSecuritySettings:
    """Monta a politica de Host e Origin aceitos.

    O SDK bloqueia por padrao qualquer Host que nao seja local — e protecao
    contra DNS rebinding, e sem ela um site malicioso poderia falar com o
    servidor pelo navegador da vitima. Servir por endereco publico exige
    declarar o dominio aqui; **nao ha curinga, a comparacao e exata**, e e por
    isso que a variavel so pode ser preenchida depois do primeiro deploy,
    quando o endereco passa a existir.
    """
    hosts = list(_LOCAIS)
    origens = [f"http://{h}" for h in _LOCAIS if "*" not in h]

    for dominio in dominios or []:
        limpo = dominio.strip().removeprefix("https://").removeprefix("http://")
        limpo = limpo.rstrip("/")
        if not limpo:
            continue
        hosts += [limpo, f"{limpo}:*"]
        origens.append(f"https://{limpo}")

    if dominios:
        origens += ["https://chatgpt.com", "https://chat.openai.com"]

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origens,
    )


INSTRUCOES = """
Legislacao do Estado do Rio de Janeiro: leis ordinarias e complementares,
emendas constitucionais, decretos legislativos e resolucoes da ALERJ, e
decretos do Poder Executivo extraidos do Diario Oficial.

Como responder ao advogado:
- Entregue a norma e a analise, nao o funcionamento da ferramenta. Nao cite
  nomes de tools nem identificadores internos. Apresente links como
  "[Texto na fonte](url)" e ponto.
- Cite no formato do campo `citacao` — e a referencia que vai para a peca.
- Todo resultado que tenha algo a declarar traz `avisos`. Leia antes de usar e
  repasse o que afetar a resposta.

A REGRA QUE NAO PODE SER QUEBRADA: VIGENCIA TEM DOIS NIVEIS

O cabecalho diz se o ATO esta em vigor. A revogacao e a inconstitucionalidade
de um DISPOSITIVO sao anotacao solta no meio do texto e **nao sobem para o
cabecalho**. A Lei 4.024/2002 consta "Em Vigor" com dois paragrafos declarados
inconstitucionais pelo Orgao Especial.

Por isso: nunca apresente uma norma como fundamento sem chamar
`verificar_vigencia`, que devolve os dois niveis. E nunca escreva "esta em
vigor" — escreva o que a fonte declara, e de onde veio a declaracao.

SILENCIO NAO E NORMA VIVA

O campo de situacao vem vazio para especies inteiras, e isso nao significa
vigencia. Medido nesta base:

    lei ordinaria          situacao no documento          10.475 de 11.123
    lei complementar       situacao so na listagem           206 de   234
    emenda constitucional  situacao so na listagem            99 de   100
    decreto legislativo    NAO HA situacao em lugar nenhum     0 de   252
    resolucao              NAO HA situacao em lugar nenhum     0 de 13.341

E o decreto do Executivo vem do Diario Oficial, que publica o ato e segue: nao
ha situacao declarada, e o texto e o do dia da publicacao.

AUSENTE NAO E INEXISTENTE

A serie de decretos vai de 42.200 (dez/2009) a 50.431, e faltam 154 dela — 17
com existencia comprovada, porque outros atos os citam. Antes de 2008 a base e
quase vazia: a fonte da ALERJ para no 42.200 e a coleta do Diario comeca em
2008. Um decreto de 2005 nao esta aqui nem como ausencia declarada.

Chame `cobertura_do_acervo` antes de afirmar que uma norma nao existe.
"""


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


def construir(
    banco: str | Path | None = None,
    dominios: list[str] | None = None,
    url_publica: str | None = None,
    segredo_oauth: str | None = None,
    **ajustes: Any,
) -> FastMCP:
    """Monta o servidor. As ferramentas nascem aqui, e nao no nivel do modulo.

    Servir por HTTP exige decidir antes de instanciar: a politica de Host
    aceito e o provedor OAuth entram na construcao do `FastMCP`, nao depois.
    """
    acervo = Acervo(Path(banco) if banco else _caminho_padrao())

    # O ChatGPT recusa servidor MCP sem OAuth; o Claude conecta sem. O fluxo so
    # e montado quando ha URL publica, porque os metadados precisam apontar
    # para enderecos que o cliente alcance.
    if url_publica:
        from .autenticacao import montar

        provedor, definicoes = montar(url_publica, segredo_oauth)
        ajustes |= {"auth_server_provider": provedor, "auth": definicoes}

    mcp = FastMCP(
        "legislacao-rj",
        instructions=INSTRUCOES,
        transport_security=seguranca_de_transporte(dominios),
        **ajustes,
    )

    @mcp.tool()
    def cobertura_do_acervo() -> dict:
        """O que este acervo tem, e principalmente o que ele NÃO tem.

        Chame antes de afirmar que uma norma não existe: a ausência aqui pode ser
        ausência da coleta, não da legislação.
        """
        return acervo.cobertura()


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
        achados = acervo.pesquisar_ementa(consulta, esp, ano, situacao, limite)
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
        achados = acervo.pesquisar_texto(consulta, esp, limite)
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

        achados = acervo.obter(esp, numero, ano)
        if not achados:
            return {
                "encontrados": 0,
                "aviso": "Não localizei este ato no acervo. Isso não prova que ele "
                "não exista: veja `cobertura_do_acervo` para o alcance da base.",
            }
        saida = []
        for ato in achados:
            registro = _resumo(ato)
            registro["vigencia"] = acervo.vigencia(ato)
            if com_texto:
                registro["texto"] = acervo.texto(ato.unid)
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
        texto = acervo.texto(id)
        if not texto:
            return {"erro": "identificador não encontrado"}
        return {
            "id": id,
            "chars": len(texto),
            "trecho": texto[de:ate],
            "continua": ate < len(texto),
        }

    return mcp
