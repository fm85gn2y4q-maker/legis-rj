"""Monta o banco do acervo: SQLite com FTS5, a partir do que já está em disco.

DUAS BUSCAS SEPARADAS, COMO NOS ACERVOS ANTERIORES

A ementa é o resumo oficial; o texto é o ato inteiro. Procurar "saneamento" na
ementa devolve as leis *sobre* saneamento; no texto, devolve também toda lei que
mencione a palavra de passagem. São perguntas diferentes e não se misturam num
índice só.

A SITUAÇÃO TEM ORIGEM, E A ORIGEM VAI JUNTO

Medido neste acervo, e é o limite mais importante dele:

    lei ordinária          situação no documento          10.475 de 11.123
    lei complementar       situação só na listagem           206 de 234
    emenda constitucional  situação só na listagem            99 de 100
    decreto legislativo    NÃO HÁ situação em lugar nenhum      0 de 252
    resolução              NÃO HÁ situação em lugar nenhum      0 de 13.341

Por isso cada ato guarda `situacao_origem`. Campo vazio numa resposta se lê como
norma viva, e para decreto legislativo e resolução a ALERJ simplesmente não
declara nada — o servidor tem de dizer isso com todas as letras, não deixar em
branco.

O QUE NÃO ENTRA NO BANCO COMO VERDADE

Divergência não vira escolha. Quando o cabeçalho e o texto do ato discordam da
data (400 atos) ou do número (10), os dois valores ficam gravados e o registro
sai marcado. Escolher um seria inventar certeza que a fonte não tem.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from extrair import extrair  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ALERJ = RAIZ / "dados" / "alerj"
DOCS = ALERJ / "docs"
BANCO = RAIZ / "dados" / "legis-rj.sqlite"

ESQUEMA = """
CREATE TABLE ato (
    unid              TEXT PRIMARY KEY,
    especie           TEXT NOT NULL,
    numero            TEXT,
    numero_ordenavel  INTEGER,
    ano               TEXT,
    data              TEXT,
    situacao          TEXT,
    situacao_origem   TEXT NOT NULL,   -- documento | listagem | ausente
    ementa            TEXT,
    autoria           TEXT,
    url               TEXT NOT NULL,
    chars             INTEGER,
    ano_inferido      INTEGER DEFAULT 0,
    numero_divergente TEXT,            -- JSON com os dois números
    data_divergente   TEXT,            -- JSON com as duas datas
    fonte             TEXT NOT NULL DEFAULT 'ALERJ',   -- ALERJ | DOERJ
    publicado_em      TEXT,            -- data da edição do Diário
    pagina            INTEGER,
    republicacoes     TEXT,            -- JSON com as outras datas de publicação
    truncado          INTEGER DEFAULT 0
);
CREATE INDEX ato_por_numero ON ato (especie, numero_ordenavel, ano);
CREATE INDEX ato_por_ano ON ato (ano);
CREATE INDEX ato_por_situacao ON ato (situacao);
CREATE INDEX ato_por_fonte ON ato (fonte);

-- Anotação de dispositivo: a revogação e a inconstitucionalidade que NÃO
-- sobem para o cabeçalho. É o segundo nível de vigência, e é onde o erro
-- custa caro: a Lei 4.024/2002 está "Em Vigor" com dois parágrafos
-- declarados inconstitucionais pelo Órgão Especial.
CREATE TABLE anotacao (
    unid    TEXT NOT NULL REFERENCES ato (unid),
    tipo    TEXT NOT NULL,   -- revogacao_expressa | nova_redacao | inconstitucionalidade
    trecho  TEXT NOT NULL
);
CREATE INDEX anotacao_por_ato ON anotacao (unid);
CREATE INDEX anotacao_por_tipo ON anotacao (tipo);

CREATE TABLE texto (
    unid   TEXT PRIMARY KEY REFERENCES ato (unid),
    texto  TEXT NOT NULL
);

-- Conteúdo externo: o índice não duplica o texto, só aponta para ele.
CREATE VIRTUAL TABLE busca_texto USING fts5(
    texto,
    content='texto',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);
CREATE VIRTUAL TABLE busca_ementa USING fts5(
    ementa,
    content='ato',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);
"""


def listagens() -> dict[str, dict]:
    """Ementa, autoria e situação como a ALERJ os mostra na lista de resultados."""
    mapa: dict[str, dict] = {}
    indice = ALERJ / "indice.jsonl"
    if indice.exists():
        for linha in indice.read_text("utf-8").splitlines():
            if not linha.strip():
                continue
            reg = json.loads(linha)
            col = reg.get("colunas", [])
            mapa[reg["unid"]] = {
                "situacao": col[2] if len(col) > 2 else "",
                "ementa": col[3] if len(col) > 3 else "",
                "autoria": col[4] if len(col) > 4 else "",
                "caminho": reg.get("caminho", ""),
            }
    situacoes = ALERJ / "situacao_especies.jsonl"
    if situacoes.exists():
        for linha in situacoes.read_text("utf-8").splitlines():
            if not linha.strip():
                continue
            reg = json.loads(linha)
            col = reg.get("colunas", [])
            atual = mapa.setdefault(reg["unid"], {})
            atual["situacao"] = reg.get("situacao_na_listagem", "") or atual.get(
                "situacao", ""
            )
            # Nas espécies sem coluna de status, a ementa anda uma casa à
            # esquerda. Pega-se a célula mais longa, que é sempre a ementa.
            texto_longo = max(col, key=len) if col else ""
            atual.setdefault("ementa", texto_longo)
            atual.setdefault("autoria", col[-1] if col else "")
    return mapa


def numero_ordenavel(numero: str | None) -> int | None:
    if not numero:
        return None
    digitos = "".join(c for c in numero if c.isdigit())
    return int(digitos) if digitos else None


DECRETOS = RAIZ / "dados" / "doerj" / "decretos.jsonl"
EDICOES = RAIZ / "dados" / "doerj" / "edicoes.jsonl"
CORPO_SUSPEITO = 300


def carregar_decretos(con: sqlite3.Connection) -> int:
    """Os decretos do Executivo, extraídos do texto do Diário Oficial.

    Entram na mesma tabela dos atos da ALERJ, com `fonte='DOERJ'` — e a
    diferença entre as duas fontes é de natureza, não de origem:

        ALERJ    declara situação; o acervo sabe se a norma foi revogada
        DOERJ    publica e segue; não há situação nenhuma, só a redação do dia

    Por isso todo decreto entra com `situacao_origem='ausente'`. Silêncio aqui
    não é "em vigor": é o Diário não ter essa informação para dar.

    REPUBLICAÇÃO É A REGRA DESTA FONTE

    345 números saem em mais de uma edição. O Estado publica com incorreção e
    republica dias depois, e nada no texto da primeira avisa. Fica gravada a
    **última** publicação, com a lista das anteriores no registro — quem
    responde precisa dizer que houve republicação, porque a versão que o
    advogado leu pode ser a de antes.
    """
    if not DECRETOS.exists():
        return 0

    edicoes = {}
    if EDICOES.exists():
        for linha in EDICOES.read_text("utf-8").splitlines():
            if linha.strip():
                reg = json.loads(linha)
                edicoes[reg["data"]] = reg.get("link", "")

    por_numero: dict[str, list[dict]] = {}
    for linha in DECRETOS.read_text("utf-8").splitlines():
        if linha.strip():
            reg = json.loads(linha)
            por_numero.setdefault(reg["numero"], []).append(reg)

    gravados = 0
    for numero, ocorrencias in por_numero.items():
        ocorrencias.sort(key=lambda r: r["data_publicacao"])
        # A última publicação manda; se ela vier truncada e houver uma inteira
        # antes, fica a inteira — o critério é ter texto, não ser recente.
        atual = ocorrencias[-1]
        if atual["chars"] < CORPO_SUSPEITO:
            inteiras = [o for o in ocorrencias if o["chars"] >= CORPO_SUSPEITO]
            if inteiras:
                atual = inteiras[-1]
        anteriores = [
            o["data_publicacao"] for o in ocorrencias if o is not atual
        ]
        unid = f"doerj:{numero}:{atual['data_publicacao']}"
        link = edicoes.get(atual["data_publicacao"], "")
        if link and atual.get("pagina"):
            link = f"{link}#page={atual['pagina']}"

        con.execute(
            "INSERT OR REPLACE INTO ato VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                unid,
                "decreto_executivo",
                numero,
                int(numero) if numero.isdigit() else None,
                (atual.get("data") or "")[:4] or None,
                atual.get("data"),
                None,
                "ausente",
                atual.get("ementa"),
                None,
                link,
                atual.get("chars"),
                0,
                None,
                None,
                "DOERJ",
                atual["data_publicacao"],
                atual.get("pagina"),
                json.dumps(anteriores, ensure_ascii=False) if anteriores else None,
                1 if atual["chars"] < CORPO_SUSPEITO else 0,
            ),
        )
        con.execute(
            "INSERT OR REPLACE INTO texto VALUES (?,?)", (unid, atual["texto"])
        )
        gravados += 1
        if gravados % 2000 == 0:
            con.commit()
            print(f"  decretos: {gravados}", flush=True)
    print(f"  {gravados} decretos do Executivo carregados")
    return gravados


def main() -> None:
    # Monta num arquivo à parte e só troca no fim. Apagar o banco antes de
    # construir deixa o servidor sem acervo durante toda a montagem — e se a
    # montagem morrer no meio, sem acervo nenhum. Aconteceu: um processo em
    # segundo plano foi morto junto com o terminal e o que sobrou foi um banco
    # de zero atos, respondendo normalmente.
    parcial = BANCO.with_suffix(".sqlite.parcial")
    if parcial.exists():
        parcial.unlink()
    con = sqlite3.connect(parcial)
    con.executescript(ESQUEMA)

    lista = listagens()
    origem = {}
    for arquivo, rotulo in (
        (ALERJ / "indice.jsonl", "lei_ordinaria"),
        (ALERJ / "indice_especies.jsonl", None),
    ):
        if arquivo.exists():
            for linha in arquivo.read_text("utf-8").splitlines():
                if linha.strip():
                    reg = json.loads(linha)
                    origem[reg["unid"]] = rotulo or reg["especie_da_view"]

    arquivos = sorted(DOCS.glob("*.html"))
    print(f"{len(arquivos)} documentos")
    atos = 0
    for i, caminho in enumerate(arquivos, 1):
        html = caminho.read_text(encoding="utf-8", errors="replace")
        reg = extrair(html, caminho.stem)
        da_lista = lista.get(caminho.stem, {})

        situacao = reg.get("situacao", "")
        situacao_origem = "documento"
        if not situacao:
            situacao = da_lista.get("situacao", "")
            situacao_origem = "listagem" if situacao else "ausente"

        con.execute(
            "INSERT OR REPLACE INTO ato VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                caminho.stem,
                origem.get(caminho.stem, "desconhecida"),
                reg.get("numero"),
                numero_ordenavel(reg.get("numero")),
                reg.get("ano"),
                reg.get("data"),
                situacao or None,
                situacao_origem,
                da_lista.get("ementa") or None,
                da_lista.get("autoria") or None,
                "https://alerjln1.alerj.rj.gov.br"
                + (da_lista.get("caminho") or f"/contlei.nsf/{caminho.stem}"),
                reg.get("chars"),
                1 if reg.get("ano_inferido") else 0,
                json.dumps(reg["numero_divergente"], ensure_ascii=False)
                if reg.get("numero_divergente")
                else None,
                json.dumps(reg["data_divergente"], ensure_ascii=False)
                if reg.get("data_divergente")
                else None,
                "ALERJ",
                None,
                None,
                None,
                0,
            ),
        )
        con.execute(
            "INSERT OR REPLACE INTO texto VALUES (?,?)", (caminho.stem, reg["texto"])
        )
        for tipo, trechos in reg.get("anotacoes", {}).items():
            con.executemany(
                "INSERT INTO anotacao VALUES (?,?,?)",
                [(caminho.stem, tipo, t) for t in trechos],
            )
        atos += 1
        if i % 2000 == 0:
            con.commit()
            print(f"  {i}/{len(arquivos)}", flush=True)

    con.commit()
    atos += carregar_decretos(con)
    con.commit()
    print("construindo os índices de busca…")
    con.execute("INSERT INTO busca_texto(busca_texto) VALUES('rebuild')")
    con.execute("INSERT INTO busca_ementa(busca_ementa) VALUES('rebuild')")
    con.commit()

    print(f"\n{atos} atos gravados em {BANCO}")
    for linha in con.execute(
        "SELECT especie, situacao_origem, COUNT(*) FROM ato "
        "GROUP BY 1, 2 ORDER BY 3 DESC"
    ):
        print(f"  {linha[2]:>6}  {linha[0]:<24} situação: {linha[1]}")
    con.close()
    if BANCO.exists():
        BANCO.unlink()
    parcial.rename(BANCO)
    print(f"banco trocado: {BANCO}")


if __name__ == "__main__":
    main()


def registrar_construcao(documentos: int) -> None:
    """Deixa em disco de quantos documentos este banco foi feito.

    Sem isso o banco envelhece calado: a coleta avança, o servidor continua
    respondendo normalmente, e ninguém percebe que ele parou de conhecer os
    atos novos. Aconteceu — o banco ficou dez dias parado em 13.463 atos
    enquanto o disco chegava a 22.755 documentos, e a única pista era eu
    conferir à mão.
    """
    import time

    (ALERJ / "banco_construido.json").write_text(
        json.dumps(
            {
                "documentos": documentos,
                "em": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def precisa_remontar() -> tuple[bool, int, int]:
    """(precisa, documentos em disco, documentos do banco atual)."""
    em_disco = sum(1 for _ in DOCS.glob("*.html"))
    marca = ALERJ / "banco_construido.json"
    if not BANCO.exists() or not marca.exists():
        return True, em_disco, 0
    construido = json.loads(marca.read_text("utf-8")).get("documentos", 0)
    return em_disco != construido, em_disco, construido
