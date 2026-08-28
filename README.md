# legis-rj — legislação do Estado do Rio de Janeiro

Repositório do futuro servidor MCP e plugin sobre a legislação estadual
fluminense: leis ordinárias, leis complementares, emendas constitucionais,
decretos legislativos, resoluções e decretos do Poder Executivo, com o que a
fonte declarar sobre revogação, alteração e inconstitucionalidade.

Segue o padrão dos acervos anteriores — Ementário do TCE-RJ, legislação de
Mesquita, pareceres da PGE-RJ, atos do CNJ: Python, SQLite com FTS5, duas
buscas separadas, acervo fora do Git.

## Estado atual

**Fase 1 — medição das fontes: feita.** Está tudo em [FONTES.md](FONTES.md),
com os números e as requisições que os produziram.

**Fase 2 — coleta e servidor: em operação.** O acervo responde por um servidor
MCP com seis ferramentas, sobre um banco de **34.138 atos**:

    25.050  ALERJ    lei ordinária, lei complementar, emenda constitucional,
                     decreto legislativo e resolução — com situação declarada
     9.088  DOERJ    decreto do Executivo, extraído do texto do Diário

A cobertura é **declarada, não presumida**: a série de decretos vai de 42.200 a
50.431 e faltam **154 (1,9%)**, dos quais 17 têm existência comprovada porque
outros atos os citam. O servidor diz isso em toda resposta que dependa disso —
"não encontrei" nunca passa por "não existe".

Dois avisos por registro, simétricos e igualmente necessários: 345 atos vêm
marcados como `truncado` (o Diário só trouxe um fragmento) e 17 com
`corpo_suspeito` (o corpo é grande demais e pode ter arrastado matéria
vizinha). Nenhum dos dois é descartado; ambos são declarados.

O que a medição mudou no plano, e continua valendo:

- **Decreto do Executivo não está na base de legislação** — e a base onde ele
  está foi abandonada. Fica em `decest.nsf`, que não aparece no menu do portal
  da ALERJ e **para no Decreto 42.200, de 22/12/2009**; o decreto estadual hoje
  está perto do 49.800. Faltam dezesseis anos. Em `contlei.nsf`, "Decreto" quer
  dizer decreto legislativo, ato da própria Assembleia.
- **Não há paginação.** Todo URL com `Start=` ou `Count=` derruba a conexão,
  inclusive os links que a própria ALERJ publica. A coleta entra pelo
  formulário de busca (POST), que aceita "Todos" — com teto de 1.000 por
  consulta, o que obriga a particionar por número de ato.
- **A vigência tem dois níveis.** O cabeçalho diz se o *ato* está em vigor; a
  revogação e a inconstitucionalidade do *dispositivo* são anotação solta no
  meio do texto e não sobem para o cabeçalho. A Lei 4.024/2002 está "Em Vigor"
  com dois parágrafos declarados inconstitucionais pelo Órgão Especial.
- **Datas em MM/DD/AAAA.** Locale do Domino. Ler como brasileiro inverte todo
  dia menor ou igual a 12, sem erro visível.
- **O buraco dos decretos tem saída pelo Diário Oficial.** O DOERJ publica um
  calendário que entrega, numa página só, **4.454 edições** com o identificador
  de cada uma, e o PDF tem **texto nativo** (13,5 mil caracteres por página) —
  sem OCR. São ~21 GB de PDF para ~1,6 GB de texto. A busca do site não serve
  para enumerar (teto de 100 resultados, sem paginação); o calendário serve.
- **Mas o Diário não anota vigência.** A base da ALERJ traz "Revogado pela Lei
  nº 5919/2011" no dispositivo; o DOERJ publica e segue. Decreto vindo do
  Diário chega na redação do dia em que saiu. Reconstruir revogação a partir
  dos decretos posteriores é inferência nossa, não declaração da fonte — e a
  resposta do servidor tem de dizer isso.

## Estrutura

```
coleta/
  alerj.py                    cliente da contlei.nsf (busca, documento, view)
  ioerj.py                    cliente do DOERJ: busca, calendário e PDF da edição
  sondar.py                   fase 1: estrutura do resultado, formato de número, teto
  sondar_documento.py         fase 1: metadados e anotações do ato
  sondar_decest.py            fase 1: a base de decretos do Executivo
  sondar_decest_cobertura.py  fase 1: até onde a série de decretos vai
  sondar_doerj.py             fase 1: caminho até o PDF e qualidade do texto
  sondar_doerj_varredura.py   fase 1: teto da busca, decretos por dia, calendário
  inventario.py               fase 1: topo de cada série normativa
medicoes/                     o que cada sondagem mediu, em JSON
dados/bruto/                  o que veio da rede, intocado (fora do Git)
```

### Onde os arquivos moram, e por quê são dois lugares

Esta máquina tem uma rotina de arquivamento que move periodicamente
`projetos\legis-rj\dados` para `D:\Acervos\projetos__legis-rj__dados` e
deixa uma junção no lugar. Ela é do usuário e roda sozinha; brigar com ela é
perder — na primeira tentativa de manter o acervo em C:, a rotina desfez a
mudança em minutos e levou junto um banco recém-montado.

Então o acervo acompanha a rotina, com uma separação deliberada:

    dados/   junção para D:\Acervos\...   PDF, texto e JSONL — onde pesa o espaço
    banco/   disco interno, fora de dados/  o SQLite — onde pesa a latência

A divisão não é estética. Medido neste acervo: abrir o banco de 182 MB e
conferir a integridade custou **24,3 s** lendo do HD USB e **1,1 s** do disco
interno. Toda pergunta que o servidor responde paga esse pedágio. E `banco/`
estar fora de `dados/` é o que impede a rotina de arquivamento de levá-lo.

Ressalva que não se apaga: neste HD o Windows já registrou erro de I/O (`disk`
ID 51), aviso de dano no log de transações do NTFS (`Ntfs` ID 140) e uma
leitura que estourou `WinError 433`. O acervo está lá por decisão do usuário,
ciente disso. O banco em C: é também o que sobra se o HD sumir no meio de uma
coleta.

## Rodar

```bash
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe coleta\sondar.py
```

O ambiente é por projeto: o Python global desta máquina carrega dependências
que se contradizem, e instalar nele quebra os servidores MCP já publicados.

### A âncora que escondia decreto, e o que ela custou

O extrator de decretos procurava o cabeçalho no **início da linha** (`^` com
`re.MULTILINE`). Em parte das edições o ato não começa a linha — vem emendado
no fio do texto, depois do título da seção e às vezes com asterisco de
republicação:

    ... circulam hoje em um só caderno  ATOS DO PODER EXECUTIVO *DECRETO Nº
    45.739 DE 23 DE AGOSTO DE 2016  ABRE CRÉDITO SUPLEMENTAR ...

Nessas edições o extrator não via **nada** e a edição inteira saía como "sem
decreto". O erro não deu sintoma nenhum: a coleta terminava, o banco montava, o
servidor respondia — e 505 decretos publicados constavam como ausentes.

Soltar a âncora, sozinho, traria a citação junto: "nos termos do Decreto nº
14.870…" casa igual. A defesa é a data que o próprio cabeçalho carrega. Medido
em 120 cadernos:

    cabeçalhos legítimos   1 a 177 dias da edição (mediana 1, p95 5)
    citações               1.053, 2.337, 2.410 e 8.893 dias

Não há nada no meio, e o corte ficou em 365 dias. A guarda vale **só** para o
cabeçalho solto: o que já entrava pela âncora continua entrando como antes,
para a correção não mudar por baixo o acervo que já tinha sido conferido.

Resultado imediato, sem baixar um único arquivo — era texto que já estava em
disco: 933 ausentes (11,3%) viraram 412 (5,0%).

E a correção do extrator destravou a coleta pela rede, que antes rendia zero.
A recuperação por Diário, que em duas rodadas trouxe **0 em 50 tentativas**,
passou a acertar **59%** com a mesma máquina e a mesma fonte — os decretos
sempre estiveram publicados; o extrator é que não os via. A série fechou em
**154 ausentes (1,9%)**.

## Coleta

Duas varreduras retomáveis, uma por fonte, rodando desde 05/08/2026:

```bash
.venv\Scripts\python.exe coleta\coletar_doerj.py
```

```bash
.venv\Scripts\python.exe coleta\coletar_alerj.py
```

Podem ser interrompidas a qualquer momento: o manifesto do DOERJ e o progresso
da ALERJ dizem onde retomar. O que já veio fica em `dados/`, fora do Git.

### Rodando sozinho

A Tarefa Agendada **legis-rj-coleta** chama `rodar.cmd` a cada 15 minutos: faz
o que falta e sai; nada pendente, sai em segundos. Log em
`dados/agendado.log`, erros em `dados/agendado_saida.log`.

Três coisas que essa tarefa aprendeu na marra, e que valem para a próxima:

- **Nasce proibida de rodar fora da tomada.** `DisallowStartIfOnBatteries` vem
  ligado por padrão, e a tarefa fica em *Enfileirados* sem nunca executar — sem
  erro nenhum. Corrigido no XML.
- **O agendador parte o caminho no espaço.** `/tr` com um caminho contendo
  "Matheus Menegatti" virou `<Command>C:\Users\Matheus</Command>` mais
  `<Arguments>Menegatti\...</Arguments>`. Registrar por XML resolve.
- **Sob o agendador não há console.** Processo que morre antes de abrir o log
  não deixa rastro, e a tarefa aparece como bem-sucedida. Por isso o `.cmd`
  registra a partida e captura o erro padrão, e o `.cmd` é ASCII puro — acento
  em linha `rem` vira comando inválido.

Para conferir ou mexer:

```bash
schtasks /query /tn legis-rj-coleta /fo LIST /v
```

Duas coisas que a coleta descobriu e que valem por si:

- **O calendário do DOERJ às vezes entrega outro caderno** — 1 página no lugar
  de 83, íntegro, sem nada que denuncie. O coletor confere cada edição contra a
  busca do dia e desvia quando falta página.
- **O teto de 1.000 da busca da ALERJ não respeita a partição por número.** Os
  números de 1 a 8 estouraram o teto, todos. Fica para depois da varredura uma
  conferência de série: número que devia existir e não apareceu volta para a
  busca combinado com o ano.

## O servidor

```bash
.venv\Scripts\python.exe testar_servidor.py
```

Registrado no Claude Desktop como `legis-rj`. Seis ferramentas, e a central é
`verificar_vigencia`, que responde **nos dois níveis**: a situação do ato e as
anotações por dispositivo, separadas.

Três decisões que valem mais que o código:

- **A situação carrega a origem.** "Em Vigor declarado no documento" e "lido da
  listagem" não são a mesma prova, e para decreto legislativo e resolução a
  ALERJ não declara nada — o servidor diz isso, em vez de devolver campo vazio,
  que se lê como norma viva.
- **Divergência da fonte não vira escolha.** Quando a ALERJ registra dois
  números para o mesmo ato, a ressalva vai **colada ao número na citação** —
  aviso em campo separado não sobrevive ao copiar e colar. E o ato é
  encontrável pelos dois números.
- **A ferramenta prova o que encontrou.** Nenhuma resposta afirma que uma norma
  está em vigor; afirma o que a fonte declarou.

## Próximo passo

Terminadas as varreduras: conferir a série da ALERJ, extrair os atos do texto
do Diário e montar o banco. As perguntas ainda em aberto estão na seção 8 de
[FONTES.md](FONTES.md).
