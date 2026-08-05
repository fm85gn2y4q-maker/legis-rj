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

## Estrutura

```
coleta/
  alerj.py             cliente HTTP da contlei.nsf (busca, documento, view)
  sondar.py            fase 1: estrutura do resultado, formato de número, teto
  sondar_documento.py  fase 1: metadados e anotações do ato
  sondar_decest.py     fase 1: a base de decretos do Executivo
  inventario.py        fase 1: topo de cada série normativa
medicoes/              o que cada sondagem mediu, em JSON
dados/bruto/           HTML como veio da rede, intocado (fora do Git)
```

## Rodar

```bash
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe coleta\sondar.py
```

O ambiente é por projeto: o Python global desta máquina carrega dependências
que se contradizem, e instalar nele quebra os servidores MCP já publicados.

## Próximo passo

Há uma decisão de escopo antes de qualquer coleta, e ela é sua: **o acervo sai
com o que a ALERJ mantém — leis, leis complementares, emendas, decretos
legislativos e resoluções — ou espera uma fonte para os decretos do Executivo
de 2010 em diante?** As duas são defensáveis; o que não é defensável é publicar
decreto com a base que parou em 2009.

Depois disso, as demais perguntas em aberto estão na seção 6 de
[FONTES.md](FONTES.md).
