"""Comprime o acervo e imprime as duas linhas que vão para o Dockerfile.

O banco não entra no Git: passa de 50 MB, é gerado por programa e muda a cada
coleta. Vai como asset de release, e a imagem o busca na construção conferindo
o sha256 — se o arquivo publicado divergir do declarado, o build falha em vez
de subir um acervo diferente daquele que foi testado.

    python preparar_release.py 1.0.0
"""

from __future__ import annotations

import gzip
import hashlib
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
BANCO = RAIZ / "banco" / "legis-rj.sqlite"


# Piso de sanidade. O acervo cresce alguns atos por semana; encolher é sinal de
# que algo deu errado antes daqui, e comprimir mesmo assim publica o defeito.
ENCOLHIMENTO_TOLERADO = 0.95


def conferir(banco: Path) -> bool:
    """Recusa comprimir um acervo vazio ou menor que o publicado.

    Escrito depois de 22/08/2026, quando a rotina agendada e uma publicação
    manual colidiram: a ingestão da rotina tinha acabado de apagar o banco para
    recriá-lo, a publicação copiou o arquivo vazio, e este programa comprimiu
    **zero ato** em 117 bytes de gzip sem reclamar. A trava em `coleta/rodar_agendado.py`
    evita a corrida; esta conferência evita a consequência, venha ela de onde
    vier.
    """
    import sqlite3

    try:
        conexao = sqlite3.connect(f"file:{banco.as_posix()}?mode=ro", uri=True)
        atos = conexao.execute("SELECT COUNT(*) FROM ato").fetchone()[0]
        conexao.close()
    except sqlite3.Error as erro:
        print(f"{banco} não é um acervo legível: {erro}", file=sys.stderr)
        return False

    if not atos:
        print(f"{banco} tem ZERO atos. Nada será comprimido.", file=sys.stderr)
        return False

    publicados = sorted((RAIZ / "acervo").glob("*.db.gz"))
    if publicados:
        from legis.comparar import abrir

        conexao, temporario = abrir(publicados[-1])
        try:
            antes = conexao.execute("SELECT COUNT(*) FROM ato").fetchone()[0]
        finally:
            conexao.close()
            if temporario:
                shutil.rmtree(temporario.parent, ignore_errors=True)

        if atos < antes * ENCOLHIMENTO_TOLERADO:
            print(f"O acervo encolheu: {antes} → {atos} atos, contra "
                  f"{publicados[-1].name}. Rode `python -m legis.comparar` "
                  f"e leia o diff antes de publicar.", file=sys.stderr)
            return False
        print(f"{atos} atos ({antes} na versão publicada).")
    else:
        print(f"{atos} atos.")
    return True


def preparar(versao: str, usuario_repo: str = "fm85gn2y4q-maker/legis-rj") -> int:
    if not BANCO.exists():
        print(f"Acervo não encontrado em {BANCO}. Rode a ingestão antes.",
              file=sys.stderr)
        return 1

    if not conferir(BANCO):
        return 1

    destino = RAIZ / "dist" / f"legislacao-rj-v{versao}.db.gz"
    destino.parent.mkdir(parents=True, exist_ok=True)

    print(f"Comprimindo {BANCO.stat().st_size / 1048576:.1f} MB…")
    with BANCO.open("rb") as entrada, gzip.open(destino, "wb", compresslevel=9) as saida:
        shutil.copyfileobj(entrada, saida, length=4 * 1024 * 1024)

    digest = hashlib.sha256(destino.read_bytes()).hexdigest()
    tamanho = destino.stat().st_size / 1048576

    print(f"\n{destino}  ({tamanho:.1f} MB)")
    print(f"\n1. Mova para acervo/ e apague o .gz anterior:\n")
    print(f"   mv {destino} acervo/")
    print("\n2. Troque no Dockerfile:\n")
    print(f"ARG ACERVO=acervo/{destino.name}")
    print(f"ARG ACERVO_SHA256={digest}")
    print("\n3. git add -A && git commit && git push — o Render reconstrói.")
    print("4. Recrie os conectores nos clientes.")
    print("\nPreferindo publicar como asset de release (para não engordar o "
          "histórico\ndo Git), o `instalar_acervo.py` também aceita URL:\n")
    print(f"ARG ACERVO=https://github.com/{usuario_repo}/releases/download/"
          f"acervo-v{versao}/{destino.name}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    raise SystemExit(preparar(sys.argv[1], *sys.argv[2:3]))
