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
    data_divergente   TEXT             -- JSON com as duas datas
);
CREATE INDEX ato_por_numero ON ato (especie, numero_ordenavel, ano);
CREATE INDEX ato_por_ano ON ato (ano);
CREATE INDEX ato_por_situacao ON ato (situacao);

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
            "INSERT OR REPLACE INTO ato VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
