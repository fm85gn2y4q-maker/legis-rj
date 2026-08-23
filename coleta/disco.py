r"""Confere que o acervo está alcançável antes de qualquer coleta.

Os dados moraram em `C:` e passaram a morar num HD externo, alcançados por uma
junção em `dados`. O caminho no código não mudou — mas a premissa mudou: agora
ele depende de um disco que pode estar desconectado.

E o modo de falhar aí é o pior possível. Sem o HD, `dados` some ou fica vazio,
e todo coletor deste projeto foi escrito para ser retomável: ao não encontrar
nada, ele conclui que não há nada coletado e **começa do zero**. Seriam 4.455
edições e 25 mil documentos baixados de novo, por cima de um acervo que está
inteiro, a um cabo de distância.

Por isso a checagem é dura: sem acervo alcançável, o processo não roda. Errar
para o lado de não fazer nada é reversível; errar para o lado de recomeçar não.
"""

from __future__ import annotations

import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"

# O acervo tem dezenas de milhares de arquivos. Estes poucos bastam para dizer
# que ele está lá — e nenhum deles se cria sozinho numa coleta nova.
MARCAS = (
    DADOS / "calendario.json",
    DADOS / "alerj" / "indice.jsonl",
    DADOS / "doerj" / "edicoes.jsonl",
)


class AcervoForaDeAlcance(RuntimeError):
    pass


def conferir() -> None:
    if not DADOS.exists():
        raise AcervoForaDeAlcance(
            f"{DADOS} não existe. O acervo vive no HD externo (D:), alcançado "
            "por uma junção. Se o HD estiver desconectado, reconecte-o — não "
            "apague a junção nem deixe a coleta rodar, ou ela recomeça do zero."
        )
    faltando = [m.name for m in MARCAS if not m.exists()]
    if faltando:
        raise AcervoForaDeAlcance(
            f"{DADOS} existe mas está sem {', '.join(faltando)}. Isso não é "
            "acervo novo, é acervo inacessível: provavelmente o HD externo não "
            "está montado. A coleta não vai rodar para não recomeçar do zero."
        )
