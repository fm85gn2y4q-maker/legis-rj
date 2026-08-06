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


PULAR_FASE_A = "PULAR_FASE_A"


def alerj(coletar_alerj) -> None:
    """Roda a coleta da ALERJ, com uma chave para inverter a ordem das fases.

    Existindo o arquivo `dados/alerj/PULAR_FASE_A`, só a fase B roda. É uma
    inversão deliberada, não um atalho: a varredura por número deixou de
    render — parou em cerca de um ato novo a cada duzentas consultas — e a
    garantia de completude não vem dela. Vem da conferência de série, que só
    pode ser feita depois de ler os documentos, porque é neles que está o
    número de cada ato. Baixar primeiro e conferir depois chega ao mesmo lugar
    fazendo só as consultas que a conferência apontar.

    O arquivo guarda em que número a varredura parou: retomá-la é apagar o
    arquivo.
    """
    indice = coletar_alerj.carregar_indice()
    a = coletar_alerj.Alerj(pausa=1.2)
    if (RAIZ / "dados" / "alerj" / PULAR_FASE_A).exists():
        anota("fase A suspensa por marcador; indo direto para os documentos")
        coletar_alerj.fase_b(a, indice)
        return
    coletar_alerj.fase_a(a, indice)
    coletar_alerj.fase_b(a, coletar_alerj.carregar_indice())


def marcar_alerj_concluida() -> None:
    """Deixa em disco o aviso de que a ALERJ fechou.

    O aviso não pode depender de haver alguém olhando: a coleta anda pela
    Tarefa Agendada, de madrugada, sem conversa nenhuma aberta. Então o fim
    fica gravado, e quem chegar depois lê o arquivo em vez de recontar tudo.

    Duas condições, e as duas precisam valer: a varredura chegou ao último
    número, e todo ato do índice tem documento em disco. Só a primeira já
    aconteceu antes com a fase B pela metade.
    """
    import json

    dados = RAIZ / "dados" / "alerj"
    progresso = dados / "progresso.json"
    indice = dados / "indice.jsonl"
    if not (progresso.exists() and indice.exists()):
        return

    import coletar_alerj

    estado = json.loads(progresso.read_text("utf-8"))
    unids = {
        json.loads(l)["unid"]
        for l in indice.read_text("utf-8").splitlines()
        if l.strip()
    }
    baixados = {p.stem for p in (dados / "docs").glob("*.html")}
    faltando = unids - baixados
    # Com a fase A suspensa, o "último número" não chega ao fim da série e
    # nunca chegaria: a régua passa a ser só a fase B, e o aviso diz até onde
    # a varredura tinha ido, para ninguém ler o arquivo como se ela tivesse
    # terminado.
    suspensa = (dados / PULAR_FASE_A).exists()
    if faltando:
        return
    if not suspensa and estado.get("ultimo_numero", 0) < coletar_alerj.MAIOR_NUMERO:
        return

    aviso = {
        "concluida_em": time.strftime("%Y-%m-%d %H:%M:%S"),
        "atos_no_indice": len(unids),
        "documentos": len(baixados),
        "fase_a_varreu_ate": estado.get("ultimo_numero", 0),
        "fase_a_suspensa": suspensa,
        "consultas_truncadas": estado.get("truncadas", []),
    }
    (dados / "CONCLUIDA.json").write_text(
        json.dumps(aviso, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    anota(f"ALERJ CONCLUÍDA: {len(unids)} atos, {len(baixados)} documentos")


def main() -> None:
    (RAIZ / "dados").mkdir(exist_ok=True)
    if not pegar_trava():
        return
    try:
        import coletar_alerj
        import enxugar_doerj

        etapa("ALERJ", lambda: alerj(coletar_alerj))
        marcar_alerj_concluida()
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
