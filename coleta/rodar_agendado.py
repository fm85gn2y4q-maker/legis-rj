"""Toca a coleta sozinho, para a máquina rodar sem ninguém olhando.

É o que a Tarefa Agendada do Windows chama a cada quinze minutos. Cada chamada
faz o que ainda falta e sai; quando não falta nada, sai em segundos. Não há
"começar de novo": todas as etapas são retomáveis por construção.

DUAS TRAVAS, E ELAS NÃO SÃO REDUNDANTES

A Tarefa Agendada já está configurada para não abrir uma segunda instância
(`IgnoreNew`). Ainda assim há o arquivo de trava aqui, porque a instância que
o agendador não conhece — a que eu subo à mão numa conversa — passaria por
cima dela. Duas coletas simultâneas gravando o mesmo `indice.jsonl` corrompem
o índice, e o estrago só apareceria muito depois.

A trava guarda o PID e é ignorada se o processo dono já morreu: máquina
desligada no meio da coleta não deixa o acervo travado para sempre.

ORDEM DAS ETAPAS

1. ALERJ, que é a que falta terminar.
2. Enxugar o DOERJ, que libera disco e confere links.

Cada etapa é isolada: uma falhando, a seguinte roda. O log fica em
`dados/agendado.log`.
"""

from __future__ import annotations

import os
import pathlib
import sys
import time
import traceback

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "coleta"))

TRAVA = RAIZ / "dados" / ".rodando"
LOG = RAIZ / "dados" / "agendado.log"


def anota(mensagem: str) -> None:
    """Grava no arquivo primeiro; a tela é o extra, não o contrário.

    A Tarefa Agendada chama por `pythonw.exe`, que não abre console — e ali
    `sys.stdout` é `None`. Um `print` comum estoura em `AttributeError` antes
    de qualquer coisa ser gravada, e o processo morre **em silêncio**: a tarefa
    aparece como executada com sucesso e não há log nenhum para desconfiar.
    Foi exatamente o que aconteceu na primeira execução.
    """
    linha = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {mensagem}"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(linha + "\n")
    if sys.stdout is not None:
        try:
            print(linha, flush=True)
        except (AttributeError, OSError, ValueError):
            pass


def processo_vivo(pid: int) -> bool:
    if pid == os.getpid():
        return False
    try:
        import subprocess

        saida = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True, timeout=30,
        ).stdout
        return str(pid) in saida
    except Exception:  # noqa: BLE001
        return True  # na dúvida, respeita a trava


def pegar_trava() -> bool:
    if TRAVA.exists():
        try:
            dono = int(TRAVA.read_text("utf-8").strip() or 0)
        except ValueError:
            dono = 0
        if dono and processo_vivo(dono):
            anota(f"já há coleta rodando (pid {dono}); saindo")
            return False
        anota(f"trava órfã do pid {dono}; assumindo")
    TRAVA.write_text(str(os.getpid()), encoding="utf-8")
    return True


def etapa(nome: str, funcao) -> None:
    anota(f"--- {nome}")
    inicio = time.monotonic()
    try:
        funcao()
        anota(f"--- {nome}: fim em {(time.monotonic() - inicio) / 60:.1f} min")
    except Exception:  # noqa: BLE001
        anota(f"--- {nome}: FALHOU\n{traceback.format_exc()}")


def main() -> None:
    (RAIZ / "dados").mkdir(exist_ok=True)
    if not pegar_trava():
        return
    try:
        import coletar_alerj
        import enxugar_doerj

        etapa("ALERJ", coletar_alerj.main)
        etapa("enxugar DOERJ", enxugar_doerj.main)
        anota("nada mais pendente nesta passada")
    finally:
        if TRAVA.exists() and TRAVA.read_text("utf-8").strip() == str(os.getpid()):
            TRAVA.unlink()


if __name__ == "__main__":
    # Sem console, uma exceção não deixa rastro nenhum. Tudo que escapar do
    # main vai para o log antes de o processo morrer.
    try:
        main()
    except BaseException:  # noqa: BLE001
        try:
            anota(f"MORREU FORA DAS ETAPAS\n{traceback.format_exc()}")
        finally:
            raise
