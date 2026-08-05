"""Cliente da busca do Diário Oficial do Estado do RJ (IOERJ).

O DOERJ não tem API. A consulta pública fica em
`www.ioerj.com.br/portal/modules/conteudoonline/busca_do.php`, e o caminho até
o texto tem quatro saltos, nenhum deles documentado:

    busca (POST)  →  view_publicacao.php  →  mostra_edicao.php?session=…
                  →  mostra_edicao.php?k=<uuid da edição>  →  PDF

O que **não** funciona, e já custou tempo: o link "Ver Texto" de cada matéria,
que apontaria para o texto avulso, devolve 404 no próprio site. Não há texto
por matéria — só o PDF da edição inteira, e a página onde a matéria saiu.

Filtro de Parte (`busca[jornal]`): 12 = Parte I (Executivo), 2 = Parte IB
(Tribunal de Contas), 5 = Parte IV (Municipalidades), 4 = Parte V.
"""

from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass
from urllib.parse import unquote

import requests

BASE = "https://www.ioerj.com.br/portal/modules/conteudoonline"
BUSCA = f"{BASE}/busca_do.php"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

PARTE_EXECUTIVO = "12"


def _decodifica(cru: bytes) -> str:
    """O site declara ISO-8859-1 e serve UTF-8. Confiar no cabeçalho enche o
    resultado de 'ResoluÃ§Ã£o' — e faz o regex de 'página' falhar calado."""
    try:
        return cru.decode("utf-8")
    except UnicodeDecodeError:
        return cru.decode("iso-8859-1")


@dataclass
class Materia:
    id: str
    data: str  # dd/mm/aaaa, como o site publica
    pagina: str
    jornal: str
    tipo: str
    href_publicacao: str


class Ioerj:
    def __init__(self, pausa: float = 1.5, timeout: int = 180):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.pausa = pausa
        self.timeout = timeout
        self._ultimo = 0.0
        self.s.get(BUSCA, timeout=timeout)  # cookie de sessão

    def _espera(self) -> None:
        delta = time.monotonic() - self._ultimo
        if delta < self.pausa:
            time.sleep(self.pausa - delta)
        self._ultimo = time.monotonic()

    def buscar(
        self,
        texto: str,
        jornal: str = PARTE_EXECUTIVO,
        dia: str = "",
        mes: str = "",
        ano: str = "",
        ordem: str = "datapublicacao desc",
    ) -> tuple[list[Materia], str]:
        """Devolve as matérias e a linha de total que o site imprime.

        Atenção ao total: o site diz quantas achou, mas **lista no máximo 10**
        e não oferece paginação nenhuma.
        """
        self._espera()
        dados = {
            "textobusca": texto,
            "busca[jornal]": jornal,
            "datapublicacao[dia]": dia,
            "datapublicacao[mes]": mes,
            "datapublicacao[ano]": ano,
            "tipobusca": "texto",
            "buscaordem": ordem,
            "buscar": "Buscar",
        }
        resp = self.s.post(
            f"{BUSCA}?acao=busca", data=dados, timeout=self.timeout,
            headers={"Referer": BUSCA},
        )
        resp.raise_for_status()
        html = _decodifica(resp.content)
        return _parse_busca(html), _linha_total(html)

    def pdf_da_edicao(self, href_publicacao: str) -> bytes:
        """Percorre os saltos até o PDF da edição em que a matéria saiu."""
        self._espera()
        r1 = self.s.get(
            _absoluto(href_publicacao), timeout=self.timeout,
            headers={"Referer": f"{BUSCA}?acao=busca"},
        )
        r1.raise_for_status()
        pagina1 = _decodifica(r1.content)
        # A página é um redirecionamento: traz o destino num <meta refresh>
        # ("1; url=/portal/…") e de novo num link "clique aqui". Capturar a
        # partir da barra, ou o "1; url=" entra junto e vira 404.
        m = re.search(r"(/portal/[^\s\"'>]*mostra_edicao[^\s\"'>]*)", pagina1)
        if not m:
            raise RuntimeError(
                f"não achei o link do visualizador em {r1.url} "
                f"({len(pagina1)} chars)"
            )
        visualizador = _absoluto(m.group(1).replace("&amp;", "&"))

        self._espera()
        r2 = self.s.get(visualizador, timeout=self.timeout, headers={"Referer": _absoluto(href_publicacao)})
        r2.raise_for_status()
        uuid = re.search(
            r"[0-9A-Fa-f]{8}-[0-9A-Za-z]{4,6}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}",
            _decodifica(r2.content),
        )
        if not uuid:
            raise RuntimeError("não achei o identificador da edição")

        self._espera()
        r3 = self.s.get(
            f"{BASE}/mostra_edicao.php?k={_chave_do_pdf(uuid.group(0))}",
            timeout=self.timeout,
            headers={"Referer": visualizador},
        )
        r3.raise_for_status()
        return r3.content


def _chave_do_pdf(pd: str) -> str:
    """O identificador impresso na página **não** é o que baixa o PDF.

    O visualizador guarda `var pd = "7A6CB79C-0463-4600-A2AA-E38A65D4B20B"` e
    pede `?k=7A6CB79C-046P3-4600-A2AA-E38A65D4B20B` — insere um `P` na posição
    12. Pedir com o identificador da página devolve 200, `text/html` e **zero
    byte**, sem erro nenhum: parece indisponibilidade da edição, e não é.

    Medido em duas edições distintas; a posição e a letra se repetiram.
    """
    return pd[:12] + "P" + pd[12:] if len(pd) > 12 else pd


def _absoluto(href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return "https://www.ioerj.com.br" + href
    return f"{BASE}/{href}"


def _linha_total(html: str) -> str:
    m = re.search(r"([\d\.]+)\s+mat[ée]rias?\s+encontradas?", html)
    return m.group(0) if m else ""


def _links_por_materia(html: str) -> dict[str, str]:
    """Os links de abertura do D.O. **não** ficam dentro do bloco da matéria:
    vêm todos juntos no fim da página. O que os liga à matéria é o parâmetro
    `i`, que é o id da matéria em base64 — `d`, `j` e `p` são a data, a Parte e
    a página, pelo mesmo caminho. O `s` é um hash do servidor: não dá para
    montar o link, só para colhê-lo.
    """
    mapa: dict[str, str] = {}
    for href in re.findall(r'href="([^"]*view_publicacao[^"]*)"', html):
        href = href.replace("&amp;", "&")
        m = re.search(r"[?&]i=([^&]+)", href)
        if not m:
            continue
        try:
            ident = base64.b64decode(unquote(m.group(1))).decode("ascii").strip()
        except (ValueError, UnicodeDecodeError):
            continue
        mapa.setdefault(ident, href)
    return mapa


def _parse_busca(html: str) -> list[Materia]:
    materias: list[Materia] = []
    links = _links_por_materia(html)
    # Cada matéria é um bloco <div class="space"> … </div> com três linhas.
    for bloco in re.split(r'<div class="space">', html)[1:]:
        ident = re.search(r"idof=#(\d+)", bloco)
        data = re.search(r"Publicada em\s*(\d{2}/\d{2}/\d{4})", bloco)
        pagina = re.search(r"na p[áa]gina\s*(\d+)", bloco)
        jornal = re.search(r"<b>Jornal:</b>\s*([^<]+)", bloco)
        tipo = re.search(r"<b>Tipo:</b>\s*([^<]+?)\s*(?:<|$)", bloco)
        if not (ident and data):
            continue
        materias.append(
            Materia(
                id=ident.group(1),
                data=data.group(1),
                pagina=pagina.group(1) if pagina else "",
                jornal=jornal.group(1).strip() if jornal else "",
                tipo=tipo.group(1).strip() if tipo else "",
                href_publicacao=links.get(ident.group(1), ""),
            )
        )
    return materias
