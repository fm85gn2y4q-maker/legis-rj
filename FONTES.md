# Fontes da legislação estadual do Rio de Janeiro — o que foi medido

Medido em 04/08/2026, contra os servidores reais. Números aqui não são
estimativa: cada um saiu de uma requisição registrada em `medicoes/`.

A regra que governa o projeto inteiro, herdada dos acervos anteriores:
**a ferramenta prova o que encontrou, não o que existe.** Num acervo de
legislação o erro caro não é deixar de achar a norma — é achar a norma
revogada e apresentá-la com a mesma confiança de uma viva.

---

## 1. O mapa das bases

A ALERJ mantém as bases em Lotus Domino, em `alerjln1.alerj.rj.gov.br`. São
bases distintas, e a divisão **não** é a que o nome sugere:

| Base | Contém | Situação |
|---|---|---|
| `contlei.nsf` | Leis ordinárias, leis complementares, emendas constitucionais, **decretos legislativos**, resoluções | medida |
| `decest.nsf` | **Decretos do Poder Executivo**, decretos-lei e resoluções do Executivo | medida — **para em dezembro de 2009** |
| `constest.nsf` | Constituição do Estado | não medida |

> **A armadilha do nome.** Em `contlei.nsf`, "Decreto" é *decreto legislativo* —
> ato da própria Assembleia, e existem 3 em 2025. O decreto do Governador, que
> é o que se cita numa peça administrativa, está em `decest.nsf`, base que **não
> aparece no menu do portal da ALERJ**. Quem procurar decreto estadual na base
> de legislação vai concluir que não existe.

### Topo de cada série (04/08/2026)

| Espécie | Mais recente | Coluna de situação na view |
|---|---|---|
| Lei ordinária | 11.293/2026 | sim (`Em Vigor`) |
| Lei complementar | 232/2026 | sim |
| Emenda constitucional | 99/2025 | sim |
| Decreto legislativo | 03/2025 | **não** |
| Resolução (ALERJ) | 2.375/2026 | **não** |
| Decreto estadual (`decest.nsf`) | **42.200, de 22/12/2009** | a medir |

A base começa em **março de 1975** — a fusão da Guanabara com o antigo Estado
do Rio. Nada anterior a isso existe aqui, e o Decreto-Lei nº 5/1975 (Código
Tributário Estadual) é o documento mais antigo que apareceu nas sondagens.

### A base de decretos parou em 2009

Sondando a série de decreto em decreto, com número de cinco dígitos (token raro,
em que a busca é confiável):

```
42.100/2009  30/10/2009   presente
42.200/2009  22/12/2009   presente
42.300 … 43.500           ausentes
44.000  45.000  46.000  47.000  48.000  49.000  49.792   ausentes
```

O decreto estadual do Rio de Janeiro está hoje perto do **49.800**. A base da
ALERJ tem até o **42.200**: faltam dezesseis anos e da ordem de **7.600
decretos** — 2010 a 2026 inteiros, o que inclui praticamente todo decreto que
se cita numa peça administrativa hoje.

> Não confundir ausência na busca com ausência na base: a consulta devolve os
> 50 mais relevantes, e um número curto como `5` não sobe ao topo mesmo
> existindo. Por isso a sondagem usou números de cinco dígitos, onde o token é
> raro o bastante para que a ausência signifique alguma coisa.

**O que isso decide.** O acervo pode prometer leis, leis complementares,
emendas, decretos legislativos e resoluções com a base da ALERJ. **Não pode
prometer decreto do Executivo** enquanto não houver fonte para 2010→2026 — e
não achei repositório oficial consolidado que a cubra: o que existe são
recortes setoriais (CGE, SEI-RJ, Fazenda) e o DOERJ dia a dia. Prometer decreto
com a base de 2009 é pior do que não prometer: devolve o texto revogado de um
decreto que já foi substituído duas vezes, com aparência impecável.

---

## 2. Como se entra: o caminho que funciona, e o que está fechado

### Fechado: paginação de view

Qualquer URL que leve `Start=` ou `Count=` **derruba a conexão** — o servidor
aceita o TCP e fecha sem enviar byte nenhum. Medido com `curl`, com `requests`,
com o navegador e pelo buscador da Anthropic: os quatro falham igual.

```
?OpenView                     → 200, 13.992 bytes
?OpenView&ExpandView          → 200, 14.052 bytes
?OpenView&Start=15            → conexão fechada
?OpenView&Count=15            → conexão fechada
?ReadViewEntries              → conexão fechada
```

Não é bloqueio contra robô: `ExpandView`, `StartKey` e `SearchMax` passam. E os
**próprios links de paginação publicados pela base** apontam para `Start=15` —
ou seja, a navegação oficial da ALERJ está quebrada, não só a nossa.

Consequência: cada view devolve as 15 linhas mais recentes e nada além. Não há
como percorrer a série de 11 mil leis por ali. `RestrictToCategory` também não
serve — a view por ano não responde a ele.

### Aberto: o formulário de busca (POST)

`contlei.nsf` — formulário desenhado, com campo de número e de autor:

```
POST /contlei.nsf/35d3e73a008ab6db83257dc50046d255?CreateDocument
     Busca, ParlamentarBusca, ProposicaoBusca, MaxResults
```

`decest.nsf` — formulário padrão do Domino:

```
POST /decest.nsf/c8ea52144c8b5c950325654c00612d63?SearchView
     Query, SearchOrder, SearchMax
```

`MaxResults=0` (ou `SearchMax=0`) significa "Todos" e devolve **o resultado
inteiro numa página só** — é o que substitui a paginação.

**Mas há teto: 1.000 documentos por consulta.** Medido nas duas bases:
`dispõe`, `estado` e `lei` devolveram exatamente 1.000 cada. Toda consulta que
bate em 1.000 está truncada e não avisa — tratar 1.000 como sinal de perda,
nunca como total.

### O que isso impõe à coleta

A enumeração tem de ser **particionada** de modo que nenhuma partição chegue a
1.000. A partição natural é o número do ato, e o formato importa:

```
ProposicaoBusca = "11.293"  →  1 documento
ProposicaoBusca = "11293"   →  0 documentos
ProposicaoBusca = "0443"    →  0 documentos
ProposicaoBusca = "443"     →  84 documentos
```

Duas coisas aí: o número **exige o ponto de milhar**, e a busca não é por campo
— `443` traz também as leis que *citam* a Lei 443, como a 8.976/2020, que
altera seu art. 60. Isso não atrapalha: enumera-se por número, deduplicando
pelo número lido no cabeçalho do próprio documento, e o excedente vira insumo
do grafo de citações.

---

## 3. O que o documento carrega

Cabeçalho, com rótulos estáveis:

```
Lei Ordinária
Lei nº    8976  /  2020
Data da Lei    08/17/2020
Texto da Lei   [ Em Vigor ]
LEI Nº 8.976 DE 17 DE AGOSTO DE 2020.
```

- **Espécie** vem do título do documento (`Lei Ordinária`), não do texto.
- **Situação** vem entre colchetes ao lado de "Texto da Lei". Valores
  observados na amostra: `Em Vigor` e `Revogado`.
- **Data em MM/DD/AAAA** — locale americano do Domino. `03/15/1975` prova o
  formato; `07/01/1981` é 1º de julho de 1981, não 7 de janeiro. Ler como
  brasileiro inverte silenciosamente todo dia ≤ 12.

### O risco central desta base: a vigência tem dois níveis

A situação do cabeçalho vale para o **ato**. As revogações e as
inconstitucionalidades que interessam a uma peça estão **por dispositivo**, como
anotação solta no corpo do texto, e não sobem para o cabeçalho.

A Lei nº 4.024/2002 está marcada `Em Vigor`. Dentro dela:

```
* Revogado pela Lei nº 5919/2011.
* Artigo 2º §§ 1º e 2º - dispositivos declarados inconstitucionais.
Em sessão do Órgão Especial, realizada em 11 de janeiro de 2010, foi declarada
a inconstitucionalidade do artigo 2º, §§ 1º e 2º e do artigo 3º da Lei
nº 4024/2002.
```

Citar "a Lei 4.024/2002, em vigor" é verdade sobre o ato e mentira sobre o
artigo 2º. **Um servidor que responda vigência olhando só o cabeçalho erra
exatamente onde o erro custa caro.** A ferramenta de vigência tem de devolver os
dois níveis, e a busca precisa alcançar a anotação do dispositivo.

### Inconstitucionalidade: existe, mas é anotação

Aparece em três formas já vistas, todas em prosa dentro do texto:

- `Norma submetida a ação de inconstitucionalidade - RI 0012003-66.1992.8.19.0000`
- `Declarado inconstitucional. Tribunal de Justiça`
- o parágrafo do Órgão Especial transcrito acima, com data de sessão e número
  de processo da ALERJ

Não é campo, não é padronizado, e **não há garantia de que a ALERJ tenha
anotado toda declaração de inconstitucionalidade** — nem as do TJRJ, nem as do
STF. O que a base prova é o que ela anotou. Confrontar com o acervo do Órgão
Especial do TJRJ e com as ADIs do STF é trabalho de outra fonte, e enquanto não
existir, a resposta tem de dizer que a ausência de anotação não é prova de
constitucionalidade.

---

## 4. Estabilidade do servidor

A cada poucas dezenas de requisições, mesmo com 1,5 s de intervalo, o servidor
fecha a conexão sem resposta (`RemoteDisconnected`). Não é bloqueio — a
requisição seguinte funciona. Sem repetição com espera crescente, uma coleta de
milhares de atos não termina; o cliente em `coleta/alerj.py` já repete cinco
vezes.

Um documento grande (Lei 443/1981, o Estatuto dos Policiais Militares) tem
261 KB de HTML. A média da amostra ficou perto de 3 KB de texto.

---

## 5. Fontes que ficaram de fora, e por quê

| Fonte | Por que não |
|---|---|
| **SILEP** (`silep.rj.gov.br`) | Só matéria de **pessoal**, e só de julho de 2017 em diante. Além disso o certificado do host não confere com o domínio. Serve como conferência pontual, não como acervo. |
| **DOERJ / IOERJ** | **Medido em 05/08/2026 — é por onde os decretos de 2010 em diante podem entrar.** Ver a seção 7. |
| **leisestaduais.com.br, LegisWeb, JusBrasil** | Bases privadas, sem garantia de proveniência nem de atualização, e o texto delas não se confere contra o original. Não entram. |
| **Portais setoriais** (CGE, SEI-RJ, Fazenda) | Recortes por assunto, em PDF avulso. Úteis para preencher buraco, não para servir de espinha dorsal. |

---

## 6. O DOERJ, medido: a varredura é viável

Pergunta que a medição da ALERJ deixou aberta: onde estão os decretos de 2010 a
2026. Resposta: no Diário
Oficial, e dá para tirá-los de lá. Medido em 05/08/2026.

### O caminho, que tem quatro saltos e uma pegadinha

```
busca (POST)  →  view_publicacao.php  →  mostra_edicao.php?session=…
              →  mostra_edicao.php?k=<identificador>  →  PDF da edição
```

O `session` é o identificador da edição em **base64 três vezes**:

```
VGpCRk1sRXd… → TjBFMlEwSTNP… → N0E2Q0I3OUMt… → 7A6CB79C-0463-4600-A2AA-E38A65D4B20B
```

E a pegadinha, que custou a tarde: **o identificador impresso na página não é o
que baixa o PDF**. O visualizador insere um `P` na posição 12 antes de pedir:

```
página:  7A6CB79C-0463 -4600-A2AA-E38A65D4B20B
pedido:  7A6CB79C-046P3-4600-A2AA-E38A65D4B20B
```

Pedir com o identificador da página devolve **200, `text/html` e zero byte** —
sem erro, sem mensagem. Parece edição indisponível, e não é. Conferido em duas
edições: mesma posição, mesma letra.

O que **não** existe: texto por matéria. O link "Ver Texto" de cada resultado
dá 404 no próprio site. Só há o PDF da edição inteira e o número da página.

### A busca tem teto de 100, e não paginar de novo

`decreto`, `estado` e `secretaria`, sem data, devolveram **exatamente 100**
cada. É teto, e não há paginação — a busca serve para achar, não para enumerar.

### O calendário é que enumera

O visualizador tem um link de calendário que devolve, **numa página só**,
`4.454` edições com o `session` de cada uma — cerca de 223 meses, de 2008/2009
a 2026. Como o `session` decodifica para o identificador da edição, essa página
basta: dela saem todos os PDFs, sem depender do índice de texto do site nem do
teto de 100.

### O texto é nativo — não precisa de OCR

Edição de 10/01/2023, Parte I:

```
4.714.965 bytes   27 páginas   365.281 caracteres   13.529 chars/página
```

13,5 mil caracteres por página é texto nativo denso. Nada de OCR — o que muda o
custo do projeto por uma ordem de grandeza.

> `pdftotext` sem `-enc UTF-8` escreve Latin-1 nesta máquina e cega toda busca
> acentuada depois, sem dar erro. Já custou caro em outro acervo.

### O custo, com os números medidos

| | |
|---|---|
| Edições a baixar | 4.454 |
| Peso por edição (amostra) | 4,7 MB |
| PDF total | ~21 GB (descartável depois da extração) |
| Texto extraído | ~1,6 GB |
| Decretos normativos por dia (3 amostras) | 10, 4 e 1 |

### O que a varredura entrega — e o que ela não entrega

Entrega **o que foi publicado**: o texto do decreto na redação em que saiu, com
data e página. É prova de publicação, que a base da ALERJ nem para as leis
oferece.

Não entrega **vigência**. Aqui está a diferença que decide como o servidor tem
de responder: a base da ALERJ traz o texto *anotado* — "Revogado pela Lei nº
5919/2011" no dispositivo. O Diário Oficial não anota nada; ele publica e segue.
Um decreto de 2013 coletado do DOERJ chega na redação de 2013, e se foi revogado
em 2019 nada no documento avisa. Dá para reconstruir parte disso lendo os
decretos posteriores e extraindo as revogações expressas — é o mesmo extrator de
referências do acervo de Mesquita — mas o resultado é **inferência nossa**, não
declaração da fonte, e tem de ser dito assim na resposta.

### O calendário não tem buraco — mas engana de outro jeito

`4.455` edições, de **31/03/2008 a 03/08/2026**. Comparando com os dias úteis de
cada ano (feriado nacional fixo descontado; móvel, não):

```
ano   edições   dias úteis   faltando   maior rombo
2010      238          255         17            3
2015      238          254         16            4
2020      241          255         14            4
2025      244          257         15            4
```

De 2009 em diante, de 10 a 18 dias úteis por ano sem edição, e o maior rombo é
de 2 a 4 dias — exatamente o tamanho de Carnaval, Sexta-feira Santa e Corpus
Christi, que ficaram de fora da conta de propósito. **Não há falha estrutural.**
(2008 só começa em 31/03, e o "rombo" de 43 dias é o começo da série.)

O engano é outro, e teria estragado a coleta inteira: **o calendário dá um link
por dia, e nem sempre é a edição inteira.**

```
01/12/2021   link do calendário: 2 páginas   busca mostra matéria na página 51
01/12/2022   link do calendário: 1 página    busca mostra matéria na página 83
```

É outro caderno, e o arquivo curto chega íntegro — nada nele denuncia a falta.
Quem confiasse no calendário coletaria um PDF de uma página e registraria o dia
como feito. Por isso o coletor confere cada edição contra a busca do próprio dia
e, sendo o PDF menor que a maior página com matéria, entra de novo pelo caminho
da busca. Nos dois casos acima o desvio trouxe 51 e 87 páginas.

### Republicação: é rotina, mas raramente alcança decreto

Uma edição por ano, de 2010 a 2026, 17 no total:

```
351 marcas de republicação, errata, retificação ou incorreção   (~21 por edição)
 10 delas a menos de 400 caracteres da palavra DECRETO          (~0,6 por edição)
```

Vinte marcas por edição confirmam que aqui é a mesma história do diário de
Mesquita: a versão errada e a corrigida saem com a mesma cara, e a busca devolve
as duas com a mesma confiança. Mas o grosso é errata de extrato de contrato e de
ato de pessoal; **decreto republicado aparece uma vez a cada duas edições**.
É pouco para inviabilizar, e é demais para ignorar: o processamento tem de casar
número de decreto com data e ficar com a última publicação, não com a primeira.

O texto continuou nativo em todos os anos da amostra — de 9,7 mil a 20,6 mil
caracteres por página. E o peso médio ficou em **3,4 MB**, não nos 4,7 MB da
primeira amostra: o acervo inteiro deve dar perto de **15 GB**, não 21.

---

## 7. A coleta, e o que ela já ensinou

Rodando desde 05/08/2026, retomável, uma varredura por fonte:

| | |
|---|---|
| `coletar_doerj.py` | 4.455 edições; PDF + texto por dia, com a conferência de completude acima |
| `coletar_alerj.py` | fase A varre os números 1..11.293 e monta o índice; fase B baixa o HTML de cada ato |

**O teto de 1.000 não respeita a partição por número.** Os oito primeiros
números — 1 a 8 — estouraram o teto, todos. Número curto aparece em citação por
todo o acervo, e a consulta volta cheia de atos que apenas o mencionam; se o
próprio ato nº 3 não estiver entre os 1.000 devolvidos, ele não entra, e nada
avisa. Só esses oito números já renderam 4.867 atos distintos.

O remédio não é refinar o padrão: é conferir depois. A série de cada espécie é
sequencial, então, terminada a varredura, sabe-se exatamente que números deviam
existir e não apareceram. Esses voltam para a busca combinados com o ano
(`ConectorProposicao=And`), que parte o resultado em pedaços que cabem no teto.
A lista de consultas truncadas fica em `dados/alerj/progresso.json`.

---

## 8. O que ainda não foi medido

Cada item aqui é uma pergunta que muda o plano se a resposta for inesperada —
não é lista de tarefas.

1. **Quantos atos existem em cada base.** O teto de 1.000 impede contar por
   busca ampla; só se sabe depois de enumerar.
3. **O conjunto fechado de valores de situação.** Vimos `Em Vigor` e
   `Revogado`. Falta saber se há `Declarado Inconstitucional`, `Sem efeito`,
   `Suspenso` — e o que a ALERJ faz com norma parcialmente revogada.
4. **A `constest.nsf`**, e se a Constituição Estadual vem com as 99 emendas
   consolidadas ou com o texto original.
5. **Quantas leis trazem anotação de dispositivo** (revogação parcial, nova
   redação, inconstitucionalidade). Na amostra de 10, seis tinham alguma marca
   de revogação. Se a proporção se confirmar, a busca por dispositivo não é
   refinamento: é o produto.
6. **Atraso da base.** A lei de ontem, publicada no DOERJ, entra aqui quando?
   Sem isso, não se pode responder "não existe norma sobre X".
