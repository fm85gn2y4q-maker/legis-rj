# Este acervo NÃO vai para o HD externo

`dados/` deve permanecer no disco interno. Não rode
`~/projetos/_migracao/migrar.py` sobre `projetos\legis-rj`.

## Por quê

O acervo esteve em `D:\Acervos\projetos__legis-rj__dados` entre 23 e 25/08/2026
e o disco falhou **três vezes** sob a carga normal da coleta. Registrado pelo
Windows em 25/08:

    6.983  disk 51     erro de I/O
       20  Ntfs 50     escrita adiada falhou
       13  disk 153    reset do dispositivo
        2  Ntfs 55     CORRUPÇÃO detectada na estrutura do sistema de arquivos

O `Ntfs 55` é o que decide: não é "não consegui ler", é dano encontrado na
estrutura do volume. As duas quedas anteriores (23 e 24/08) traziam só `disk
51` e `Ntfs 140`.

Cada queda matou a coleta em andamento — uma delas com a recuperação de
decretos em 45% de acerto, no melhor momento dela. O acervo sobreviveu porque
toda escrita aqui é atômica (arquivo parcial e troca no fim) e porque conferi
os JSONL depois de cada tombo. Isso é sorte administrada, não garantia.

## O que continua valendo do desenho antigo

O banco `banco/legis-rj.sqlite` fica **fora** de `dados/`, no disco rápido —
medido: abrir e conferir o banco custava 24,3 s lendo do USB contra 1,1 s do
disco interno. Essa separação é boa por si e não depende de onde `dados/` está.

A pasta `cadernos/`, irmã de `dados/`, existe pelo mesmo motivo e também fica
fora.

## Se o espaço em C: apertar

Antes de cogitar o HD externo de novo: `coleta/enxugar_doerj.py` descarta o PDF
das edições cujo texto já foi extraído, e o link original de cada ato continua
respondível pelo IOERJ. O acervo foi desenhado para isso.

Uma cópia de 25/08/2026 continua em `D:\Acervos\projetos__legis-rj__dados`.
Serve como backup frio — **não** como fonte para restaurar por cima, porque a
coleta seguiu depois dela.
