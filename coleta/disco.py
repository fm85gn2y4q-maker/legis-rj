r"""Confere que o acervo está alcançável antes de qualquer coleta.

O acervo mora em `C:`. Já morou num HD externo por algumas horas, em
23/08/2026, e voltou: o disco registrou erro de I/O e aviso de possível dano no
log de transações do NTFS.

Esta checagem continua valendo, e por um motivo que não é o disco externo. A
máquina tem uma **rotina de arquivamento** que move pastas de dados de projeto
para `D:\Acervos\`, com nome achatado — foi ela que partiu este acervo em dois
lugares naquele dia. Se ela passar de novo por aqui, `dados` some do caminho de
sempre.

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
            f"{DADOS} não existe. O acervo vive aqui mesmo, no disco interno. "
            "Se sumiu, provavelmente a rotina de arquivamento o levou para "
            "D:\Acervos\projetos__legis-rj__dados — traga de volta antes de "
            "deixar a coleta rodar, ou ela recomeça do zero."
        )
    faltando = [m.name for m in MARCAS if not m.exists()]
    if faltando:
        raise AcervoForaDeAlcance(
            f"{DADOS} existe mas está sem {', '.join(faltando)}. Isso não é "
            "acervo novo, é acervo incompleto — foi assim que ele apareceu "
            "quando metade dele tinha sido movida para outro lugar. A coleta "
            "não vai rodar, para não recomeçar do zero por cima do que existe."
        )
