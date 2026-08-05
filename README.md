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
com os números e as requisições que os produziram. Nada de coleta em massa foi
executado ainda.

O que a medição já mudou no plano:

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

## Rodar

```bash
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe coleta\sondar.py
```

O ambiente é por projeto: o Python global desta máquina carrega dependências
que se contradizem, e instalar nele quebra os servidores MCP já publicados.

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

Duas coisas que a coleta descobriu e que valem por si:

- **O calendário do DOERJ às vezes entrega outro caderno** — 1 página no lugar
  de 83, íntegro, sem nada que denuncie. O coletor confere cada edição contra a
  busca do dia e desvia quando falta página.
- **O teto de 1.000 da busca da ALERJ não respeita a partição por número.** Os
  números de 1 a 8 estouraram o teto, todos. Fica para depois da varredura uma
  conferência de série: número que devia existir e não apareceu volta para a
  busca combinado com o ano.

## Próximo passo

Terminadas as varreduras: conferir a série da ALERJ, extrair os atos do texto
do Diário e montar o banco. As perguntas ainda em aberto estão na seção 8 de
[FONTES.md](FONTES.md).
