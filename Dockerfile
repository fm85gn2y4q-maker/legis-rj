# Imagem do servidor de legislacao do Estado do RJ (Render, Cloud Run, Fly).
FROM python:3.12-slim

WORKDIR /app

# As dependencias mudam menos que o codigo: instaladas antes, para aproveitar o
# cache entre construcoes.
COPY requirements-servidor.txt ./
RUN pip install --no-cache-dir -r requirements-servidor.txt

COPY legis_rj/ ./legis_rj/

# O ACERVO VEM DE UM RELEASE, E NAO DO REPOSITORIO
#
# O projeto irmao (legis-mesquita) embute o acervo no Git, e tem razao: sao 21
# MB numa base que se recoleta uma ou duas vezes por ano, e vindo pelo Git
# somem tres modos de falha (repositorio privado devolvendo 404, asset errado
# anexado, URL divergente do nome do repositorio) alem da dependencia de rede.
#
# Aqui a conta e outra. Sao 66 MB e a coleta roda a cada duas horas: cada
# versao publicada ficaria para sempre no historico do Git, que nao esquece.
# Por isso o acervo vai como asset de release — e o repositorio e publico, o
# que elimina justamente o modo de falha do 404.
#
# O que NAO muda e a cadeia de integridade: o sha256 e declarado aqui e
# conferido ANTES de descomprimir. Divergindo o arquivo, a construcao falha em
# vez de subir um acervo diferente daquele que foi testado. Publicar acervo
# novo e rodar `python preparar_release.py <versao>`, subir o asset e trocar
# estas duas linhas.
#
# Gerado por `python preparar_release.py 1.1.0`: 34.138 atos, 192 -> 65 MB.
ARG ACERVO=https://github.com/fm85gn2y4q-maker/legis-rj/releases/download/acervo-v1.1.0/legislacao-rj-v1.1.0.db.gz
ARG ACERVO_SHA256=a7870d437a53efb2cfe3789543f55925d4fa60c8bdd0dc0265c6ef9ceef86cb4
COPY instalar_acervo.py ./
RUN python instalar_acervo.py "$ACERVO" banco/legis-rj.sqlite "$ACERVO_SHA256"

# O servico define a porta; 8080 e o padrao quando ele nao define.
ENV PORT=8080     LEGIS_RJ_HOST=0.0.0.0     LEGIS_RJ_BANCO=/app/banco/legis-rj.sqlite     PYTHONUTF8=1     PYTHONUNBUFFERED=1

EXPOSE 8080

# LEGIS_RJ_DOMINIOS e definido depois do primeiro deploy, quando o endereco
# publico passa a existir. Sem ele, so requisicoes locais sao aceitas — o que
# na pratica significa que o servico responde 421 a tudo.
CMD ["python", "-m", "legis_rj", "--http"]
