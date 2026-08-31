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
# O banco NÃO mora junto com a matéria-prima, e a razão é medida:
# `dados/` é junção para o HD externo, e ler o SQLite de lá custou 24 s só para
# abrir o arquivo; no disco rápido, 1 s. Vale para toda pergunta que o servidor
# responde. PDF e JSONL ficam no HD, que é onde o espaço importa; o banco fica
# em C:, que é onde a latência importa. E `banco/` está fora de `dados/`, então
# a rotina de arquivamento da máquina não o leva junto.
BANCO = RAIZ / "banco" / "legis-rj.sqlite"

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
    truncado          INTEGER DEFAULT 0,
    corpo_suspeito    TEXT             -- por que o corpo deste registro não é confiável
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


# A LISTAGEM NEM SEMPRE TRAZ A COLUNA DE SITUACAO
#
# O normal e cinco colunas — numero, ano, situacao, ementa, autoria. Mas em 45
# linhas a ALERJ manda quatro, sem a situacao, e a leitura por posicao fixa nao
# percebe: o que entra no campo de situacao e a EMENTA, e no de ementa entra a
# autoria. A linha inteira anda uma casa.
#
# Ninguem via erro. O ato respondia com "situacao: CRIA O MUNICIPIO DE ARMACAO
# DOS BUZIOS, A SER DESMEMBRADO DO MUNICIPIO DE CABO FRIO" — texto que nao e
# situacao nenhuma, mas preenche o campo e o faz parecer declarado.
#
# Por isso a coluna nao se le por posicao: le-se pelo CONTEUDO. A situacao vem
# de um vocabulario fechado e curto; o que nao esta nele nao e situacao, e a
# linha entao tem quatro colunas.
SITUACOES_DECLARADAS = {
    "Em Vigor",
    "Revogado",
    "Declarado Inconstitucional",
    "Em Vigor com alterações",
    "Suspenso",
    "Declarado Parcialmente Inconstitucional",
    "Trabalhando o texto",
}


def _colunas(col: list) -> dict:
    """Situação, ementa e autoria — conforme a linha tenha ou não a situação."""
    tem_situacao = len(col) > 2 and str(col[2]).strip() in SITUACOES_DECLARADAS
    deslocamento = 0 if tem_situacao else -1
    def pega(i: int) -> str:
        j = i + deslocamento
        return str(col[j]).strip() if 0 <= j < len(col) else ""
    return {
        "situacao": pega(2) if tem_situacao else "",
        "ementa": pega(3),
        "autoria": pega(4),
    }


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
                **_colunas(col),
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


# O consolidado junta a varredura do calendário, os cadernos das edições
# extras e o que a recuperação por data trouxe. Ler o arquivo da varredura
# sozinho deixaria de fora tudo o que foi recuperado — e sem erro nenhum: o
# banco ficaria menor e ninguém notaria.
DECRETOS_CONSOLIDADO = RAIZ / "dados" / "doerj" / "decretos_todos.jsonl"
DECRETOS = RAIZ / "dados" / "doerj" / "decretos.jsonl"
EDICOES = RAIZ / "dados" / "doerj" / "edicoes.jsonl"
CORPO_SUSPEITO = 300
# Acima disto o corpo quase certamente arrastou material que não é do ato. Não
# se descarta o registro: 31 de 11.200 passam daqui, e parte é legítima — o
# Decreto 49.643/2025 é o Regulamento de Inspeção Industrial inteiro, 305 mil
# caracteres de verdade. Mas o 41.021 tem 217 mil porque o cabeçalho casou
# dentro de um índice de anexos, e a fronteira que o Diário imprime só aparece
# depois de tudo. Como não dá para separar os dois com segurança, o registro
# entra e **avisa** — que é o que esta base faz quando não sabe.
CORPO_LONGO_DEMAIS = 100_000
# Quanto do maior texto conhecido de um número uma ocorrência precisa ter para
# ser considerada o ato, e não uma menção a ele. Metade é folgado: republicação
# corrigida costuma variar pouco de tamanho, e menção fica uma ordem de
# grandeza abaixo.
FRACAO_MINIMA_DA_MAIOR = 0.5


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
    fonte = DECRETOS_CONSOLIDADO if DECRETOS_CONSOLIDADO.exists() else DECRETOS
    if not fonte.exists():
        return 0

    edicoes = {}
    if EDICOES.exists():
        for linha in EDICOES.read_text("utf-8").splitlines():
            if linha.strip():
                reg = json.loads(linha)
                edicoes[reg["data"]] = reg.get("link", "")

    por_numero: dict[str, list[dict]] = {}
    for linha in fonte.read_text("utf-8").splitlines():
        if linha.strip():
            reg = json.loads(linha)
            por_numero.setdefault(reg["numero"], []).append(reg)

    gravados = 0
    for numero, ocorrencias in por_numero.items():
        ocorrencias.sort(key=lambda r: r["data_publicacao"])
        # A ÚLTIMA PUBLICAÇÃO MANDA — MAS SÓ ENTRE AS QUE SÃO O ATO
        #
        # A regra existe porque republicação corrige: sai com incorreção, sai
        # de novo dias depois, e vale a segunda. O que ela não previa é que
        # nem toda ocorrência posterior é uma republicação — muitas são
        # menção, errata de uma linha ou entrada de sumário.
        #
        # Medido: o Decreto 44.584/2014, que altera cinco livros do RICMS,
        # aparece quatro vezes — 197.441, 222.221, 2.786 e **371** caracteres.
        # A última é uma nota, e era ela que estava no banco. O acervo dizia
        # ter o decreto e entregava um fragmento, sem nada acusando.
        #
        # O piso de 300 caracteres não pegava isso: 371 passa. O piso certo é
        # relativo — uma republicação de verdade tem porte parecido com o do
        # ato; um fragmento tem uma fração dele.
        maior = max(o["chars"] for o in ocorrencias)
        piso = max(CORPO_SUSPEITO, int(maior * FRACAO_MINIMA_DA_MAIOR))
        candidatas = [o for o in ocorrencias if o["chars"] >= piso]
        atual = candidatas[-1] if candidatas else ocorrencias[-1]
        # Republicação é sair em EDIÇÕES diferentes. A mesma edição extraída de
        # cadernos diferentes gera ocorrências repetidas, e listá-las fazia o
        # servidor anunciar "publicado mais de uma vez: 2012-05-30, 2012-05-30,
        # 2012-05-30..." — alarme falso sobre um ato que saiu uma vez só, e que
        # levaria o advogado a duvidar do texto sem motivo.
        anteriores = sorted(
            {
                o["data_publicacao"]
                for o in ocorrencias
                if o["data_publicacao"] != atual["data_publicacao"]
            }
        )
        unid = f"doerj:{numero}:{atual['data_publicacao']}"
        link = edicoes.get(atual["data_publicacao"], "")
        if link and atual.get("pagina"):
            link = f"{link}#page={atual['pagina']}"

        con.execute(
            "INSERT OR REPLACE INTO ato VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
                (
                    f"corpo de {atual['chars']} caracteres, muito acima do "
                    f"normal para um decreto; a fronteira do ato foi decidida "
                    f"por '{atual.get('fronteira', 'desconhecida')}' e pode ter "
                    f"arrastado matéria vizinha"
                )
                if atual["chars"] > CORPO_LONGO_DEMAIS
                else None,
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
    BANCO.parent.mkdir(parents=True, exist_ok=True)
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
            "INSERT OR REPLACE INTO ato VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
                None,   # corpo_suspeito: só vale para decreto do DOERJ
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
    # A marca é gravada AQUI, depois da troca — só o banco que ficou em pé
    # pode dizer de que material foi feito. Ela ficou uma semana congelada em
    # 21/08 porque esta chamada não existia: a função estava escrita, comentada
    # e morta. O efeito não foi banco velho, foi o contrário — a comparação
    # nunca batia e a tarefa remontava o acervo inteiro a cada duas horas,
    # nove vezes em três dias, sem nada no log parecendo errado.
    registrar_construcao()
    print(f"banco trocado: {BANCO}")



def _impressao_digital() -> dict:
    """O que o banco precisa refletir: documentos da ALERJ e registros de decreto.

    Comparar só os documentos da ALERJ deixava a remontagem cega para a
    recuperação de decretos — ela poderia trazer 500 atos novos e o banco
    continuaria "em dia", porque a contagem que ele vigiava não tinha mudado.
    """
    fonte = DECRETOS_CONSOLIDADO if DECRETOS_CONSOLIDADO.exists() else DECRETOS
    decretos = 0
    if fonte.exists():
        decretos = sum(1 for l in fonte.read_text("utf-8").splitlines() if l.strip())
    return {
        "documentos": sum(1 for _ in DOCS.glob("*.html")),
        "registros_de_decreto": decretos,
    }


def registrar_construcao() -> None:
    """Deixa em disco de que material este banco foi feito.

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
                **_impressao_digital(),
                "em": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def precisa_remontar() -> tuple[bool, dict, dict]:
    """(precisa, o que há em disco, o que o banco reflete)."""
    agora = _impressao_digital()
    marca = ALERJ / "banco_construido.json"
    if not BANCO.exists() or not marca.exists():
        return True, agora, {}
    construido = json.loads(marca.read_text("utf-8"))
    igual = all(construido.get(k) == v for k, v in agora.items())
    return not igual, agora, construido


# A entrada fica no FIM do arquivo, e nao no meio.
#
# Ela estava logo depois de `main()`, antes das funcoes que `main()` usa. Como
# o modulo executa de cima para baixo, `main()` era chamada com
# `registrar_construcao` ainda por definir — e o processo montava o banco
# inteiro, trocava o arquivo e so entao morria com NameError, deixando a marca
# por gravar. Custou uma montagem completa para aparecer, porque o erro estava
# na ULTIMA linha do caminho feliz.
if __name__ == "__main__":
    main()
