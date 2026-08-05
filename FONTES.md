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
| **DOERJ / IOERJ** | É a fonte **autoritativa** do que foi publicado, mas é PDF de edição diária, sem consulta por norma, e a varredura é dia a dia. É o lugar certo para conferir uma republicação ou um decreto recentíssimo — não para montar a base. |
| **leisestaduais.com.br, LegisWeb, JusBrasil** | Bases privadas, sem garantia de proveniência nem de atualização, e o texto delas não se confere contra o original. Não entram. |
| **Portais setoriais** (CGE, SEI-RJ, Fazenda) | Recortes por assunto, em PDF avulso. Úteis para preencher buraco, não para servir de espinha dorsal. |

---

## 6. O que ainda não foi medido

Cada item aqui é uma pergunta que muda o plano se a resposta for inesperada —
não é lista de tarefas.

1. **Onde estão os decretos de 2010 a 2026.** É a pergunta que sobrou da
   medição da `decest.nsf`, e a única que muda o escopo do acervo. Candidatos, e
   o que precisa ser medido em cada um: o **DOERJ** pela IOERJ (autoritativo,
   mas é PDF de edição diária — dá para varrer 16 anos?); os portais setoriais
   (cobrem só a própria matéria — quanto do total?); e a hipótese de haver
   repositório oficial que eu não localizei.
2. **Quantos atos existem em cada base.** O teto de 1.000 impede contar por
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
