r"""Confere que o acervo está alcançável antes de qualquer coleta.

O acervo mora em `C:`, e isso é decisão tomada com medida na mão. Ele esteve em
`D:\Acervos\projetos__legis-rj__dados` entre 23 e 25/08/2026 e o disco derrubou
a coleta três vezes. Na terceira, o Windows registrou 6.983 erros `disk` 51 e
dois `Ntfs` **55** — corrupção encontrada na estrutura do volume, não erro de
leitura. Ver `NAO-MIGRAR.md` na raiz.

Esta checagem continua valendo, e por um motivo que não é o disco. A máquina
tem `~/projetos/_migracao/migrar.py`, que sessões do Claude rodam para levar a
pasta de dados de um projeto para `D:\Acervos\`, deixando junção no lugar. Se
alguém o rodar sobre este projeto, `dados` volta para o disco ruim.

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
            "Se sumiu, provavelmente alguém rodou _migracao/migrar.py e o "
            r"levou para D:\Acervos\projetos__legis-rj__dados — traga de "
            "volta antes de deixar a coleta rodar, ou ela recomeça do zero. "
            "E leia NAO-MIGRAR.md antes: aquele disco corrompeu."
        )
    faltando = [m.name for m in MARCAS if not m.exists()]
    if faltando:
        raise AcervoForaDeAlcance(
            f"{DADOS} existe mas está sem {', '.join(faltando)}. Isso não é "
            "acervo novo, é acervo incompleto — foi assim que ele apareceu "
            "quando metade dele tinha sido movida para outro lugar. A coleta "
            "não vai rodar, para não recomeçar do zero por cima do que existe."
        )
