# Publicar o servidor no Render

O deploy é seu porque não há credencial do Render nesta máquina. O que segue
já está pronto e verificado no que dava para verificar aqui; o que não deu está
dito ao final.

## 1. Criar o serviço

Dashboard do Render → **Blueprints** → **New Blueprint** → apontar para
`https://github.com/fm85gn2y4q-maker/legis-rj`.

Ele lê o [`render.yaml`](render.yaml) e cria um serviço web `legislacao-rj` no
plano gratuito, construído pelo [`Dockerfile`](Dockerfile).

O primeiro deploy **vai subir e não vai responder a ninguém de fora**. Isso é
esperado, e é o item 2.

## 2. Preencher as variáveis, depois do primeiro deploy

Só depois de existir o endereço público (`legislacao-rj-XXXX.onrender.com`):

| variável | valor |
|---|---|
| `LEGIS_RJ_DOMINIOS` | `legislacao-rj-XXXX.onrender.com` (sem `https://`) |
| `LEGIS_RJ_URL_PUBLICA` | `https://legislacao-rj-XXXX.onrender.com` |
| `LEGIS_RJ_SEGREDO_OAUTH` | gerado pelo próprio Render — não mexa |

**Por que não dá para preencher antes:** o SDK bloqueia qualquer `Host` que não
seja local, como proteção contra DNS rebinding, e **a comparação é exata, sem
curinga**. Sem `LEGIS_RJ_DOMINIOS`, toda requisição externa recebe `421`.
Testado aqui: requisição local devolve `200`, requisição com `Host` forjado
devolve `421`.

`LEGIS_RJ_URL_PUBLICA` liga o fluxo OAuth, que o **ChatGPT exige** para aceitar
um conector. O **Claude conecta sem ele** — se você só for usar no Claude, pode
deixar em branco.

Salvar as variáveis redeploya sozinho.

## 3. Conectar

- **Claude**: Configurações → Conectores → adicionar servidor MCP remoto, com
  `https://legislacao-rj-XXXX.onrender.com/mcp`.
- **ChatGPT**: Configurações → Conectores → o mesmo endereço. Ele fará o fluxo
  OAuth.

## Publicar acervo novo

```bash
python preparar_release.py 1.1.0
gh release create acervo-v1.1.0 dist/legislacao-rj-v1.1.0.db.gz
```

Depois troque as duas linhas `ARG ACERVO=` e `ARG ACERVO_SHA256=` do
`Dockerfile` e faça push — o Render reconstrói sozinho.

O sha256 é conferido **antes** de descomprimir: divergindo o arquivo, a
construção falha em vez de subir um acervo diferente do que foi testado.

## O que foi verificado aqui, e o que não foi

Verificado:

- o download do acervo pelo release, com conferência de sha256 e descompressão
  — é o passo exato que o `Dockerfile` executa, e o banco resultante tem os
  34.138 atos;
- o servidor em `--http`, respondendo `200` no `initialize` e `421` a `Host`
  forjado;
- o plugin `.mcpb` pelo protocolo, com as seis ferramentas e uma consulta real.

**Não** verificado, por não haver Docker nesta máquina: a construção da imagem.
O `Dockerfile` segue o do projeto irmão, que está em produção, e a única
diferença de fundo é a origem do acervo (release em vez de arquivo do
repositório) — que é justamente o passo testado acima, fora da imagem. Se o
build falhar, o log do Render dirá em qual linha.

## Sobre `healthCheckPath`

Fica fora do `render.yaml` **de propósito**. O Render só considera saudável um
`GET` que devolva 2xx, e este servidor responde `406` em `GET /mcp`, `404` em
`GET /` e `200` só em `POST /mcp`. Declarar a chave deixaria o serviço
eternamente "unhealthy" e o deploy falharia sem dizer por quê — aconteceu no
projeto irmão.
