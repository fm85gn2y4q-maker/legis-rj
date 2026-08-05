"""Cliente HTTP da base CONTLEI da ALERJ (Lotus Domino).

O que esta base é: `contlei.nsf` guarda a legislação estadual do Rio de Janeiro
desde março de 1975 — leis ordinárias, leis complementares, emendas
constitucionais, decretos legislativos e resoluções da Assembleia. **Decreto do
Poder Executivo não está aqui**; "Decreto" nesta base é decreto legislativo.

Duas restrições medidas no servidor (ver FONTES.md) e que determinam o desenho:

1. Qualquer URL com os parâmetros `Start=` ou `Count=` derruba a conexão — o
   servidor aceita o TCP e fecha sem resposta. Isso vale para o navegador
   também, e inclui os próprios links de paginação que a base publica. Ou seja:
   **não há como paginar uma view**; cada view devolve as primeiras 15 linhas e
   acabou.
2. O formulário de busca (POST) aceita `MaxResults=0` = "Todos", e devolve o
   resultado inteiro numa página só. É por ele que se enumera.

Por isso a coleta não percorre views: consulta o formulário de busca.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

BASE = "https://alerjln1.alerj.rj.gov.br/contlei.nsf"

# Documento do formulário de busca do Domino. Chegamos nele por
# /contlei.nsf/<view>/$searchForm?SearchView — todas as views apontam para o
# mesmo, e a busca varre a base inteira, não só a view de origem.
FORM_BUSCA = f"{BASE}/35d3e73a008ab6db83257dc50046d255?CreateDocument"

# Views por espécie normativa, colhidas do portal www3.alerj.rj.gov.br.
# São formulários (?OpenForm) com view embutida; servem para descobrir o topo
# de cada série (o número mais recente), não para enumerar.
VIEWS = {
    "lei_ordinaria": "LeiOrdInt",
    "lei_complementar": "LeiCompInt",
    "emenda_constitucional": "EmendaInt",
    "decreto_legislativo": "DecretoInt",
    "resolucao": "ResolucaoInt",
    "geral": "GeralInt",
}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# O servidor não declara charset e não é coerente: a página de resultado da
# busca vem em UTF-8, e as views de formulário (?OpenForm) vêm em ISO-8859-1.
# Decidir por página, não por servidor — fixar um dos dois estraga o outro
# silenciosamente (vira "AÇÕES" ou "AÃ\x87Ã\x95ES", conforme o lado do erro).
def _decodifica_bytes(cru: bytes) -> str:
    try:
        return cru.decode("utf-8")
    except UnicodeDecodeError:
        return cru.decode("iso-8859-1")


@dataclass
class Resultado:
    """Uma linha da página de resultado da busca."""

    unid: str
    caminho: str = ""  # href como veio: /contlei.nsf/<view>/<unid>?OpenDocument
    numero: str = ""
    ano: str = ""
    status: str = ""
    ementa: str = ""
    autoria: str = ""
    colunas: list[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        # O Domino exige o contexto da view: /contlei.nsf/<unid> sozinho dá 500.
        if self.caminho:
            return "https://alerjln1.alerj.rj.gov.br" + self.caminho
        return f"{BASE}/{self.unid}?OpenDocument"


class Alerj:
    def __init__(self, pausa: float = 1.0, timeout: int = 180):
        self.sessao = requests.Session()
        self.sessao.headers["User-Agent"] = UA
        self.pausa = pausa
        self.timeout = timeout
        self._ultimo = 0.0

    def _espera(self) -> None:
        delta = time.monotonic() - self._ultimo
        if delta < self.pausa:
            time.sleep(self.pausa - delta)
        self._ultimo = time.monotonic()

    def _decodifica(self, resp: requests.Response) -> str:
        return _decodifica_bytes(resp.content)

    def _pedir(self, metodo: str, url: str, **kw) -> requests.Response:
        """Um pedido, com repetição.

        Medido: o servidor derruba a conexão sem resposta a cada poucas
        dezenas de pedidos, mesmo com 1,5 s de intervalo — não é bloqueio, é
        instabilidade. Sem repetir, uma coleta de 11 mil atos não termina.
        """
        ultimo: Exception | None = None
        for tentativa in range(5):
            self._espera()
            try:
                resp = self.sessao.request(metodo, url, timeout=self.timeout, **kw)
                resp.raise_for_status()
                return resp
            except (requests.ConnectionError, requests.Timeout) as exc:
                ultimo = exc
                time.sleep(2 * (tentativa + 1) ** 2)
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code < 500:
                    raise
                ultimo = exc
                time.sleep(2 * (tentativa + 1) ** 2)
        raise RuntimeError(f"5 tentativas falharam em {url}") from ultimo

    # ------------------------------------------------------------------ busca

    def buscar(
        self,
        texto: str = "",
        numero: str = "",
        autor: str = "",
        max_results: int = 0,
    ) -> list[Resultado]:
        """POST no formulário de busca. `max_results=0` é "Todos"."""
        dados = {
            "Busca": texto,
            "%%Surrogate_ConectorParlamentar": "1",
            "ConectorParlamentar": "Or",
            "ParlamentarBusca": autor,
            "%%Surrogate_ConectorProposicao": "1",
            "ConectorProposicao": "OR",
            "ProposicaoBusca": numero,
            "%%Surrogate_MaxResults": "1",
            "MaxResults": str(max_results),
        }
        resp = self._pedir("POST", FORM_BUSCA, data=dados)
        return self._parse_resultados(self._decodifica(resp))

    @staticmethod
    def _parse_resultados(html: str) -> list[Resultado]:
        sopa = BeautifulSoup(html, "html.parser")
        achados: list[Resultado] = []
        for linha in sopa.find_all("tr"):
            link = linha.find(
                "a", href=re.compile(r"OpenDocument", re.IGNORECASE)
            )
            if not link:
                continue
            href = link.get("href", "")
            unid = _unid_da_href(href)
            if not unid:
                continue
            celulas = [
                " ".join(td.get_text(" ", strip=True).split())
                for td in linha.find_all("td")
            ]
            celulas = [c for c in celulas if c]
            achados.append(
                Resultado(
                    unid=unid,
                    caminho=href,
                    colunas=celulas,
                    ementa=_maior(celulas),
                )
            )
        return achados

    # -------------------------------------------------------------- documento

    def documento(self, alvo: "str | Resultado") -> str:
        """HTML cru do ato. Não interpreta: coletar e processar são fases
        separadas, e o que veio da rede fica intocado.

        Aceita um `Resultado` (traz o caminho com a view) ou uma URL inteira.
        """
        url = alvo.url if isinstance(alvo, Resultado) else alvo
        return self._decodifica(self._pedir("GET", url))

    def view(self, nome: str) -> str:
        """HTML de uma view/formulário (só as 15 primeiras linhas — ver módulo)."""
        return self._decodifica(self._pedir("GET", f"{BASE}/{nome}?OpenForm"))


def _unid_da_href(href: str) -> str:
    partes = [p for p in href.split("?")[0].split("/") if p]
    if not partes:
        return ""
    candidato = partes[-1]
    return candidato if re.fullmatch(r"[0-9a-fA-F]{32}", candidato) else ""


def _maior(celulas: list[str]) -> str:
    return max(celulas, key=len) if celulas else ""
