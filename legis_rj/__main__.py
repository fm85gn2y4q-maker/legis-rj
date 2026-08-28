"""Entrada do servidor MCP da legislacao estadual do Rio de Janeiro.

    python -m legis_rj                # stdio, para o Claude
    python -m legis_rj --http         # HTTP em 127.0.0.1:8765, para o ChatGPT
"""

from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m legis_rj",
        description="Servidor MCP sobre a legislacao do Estado do Rio de Janeiro.",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="serve por HTTP em vez de stdio (necessario para o ChatGPT)",
    )
    # Em hospedagem, host/porta/dominio vem do ambiente: o servico sorteia a
    # porta (PORT e o padrao do Render, do Cloud Run e afins) e o endereco
    # publico so se conhece depois do primeiro deploy.
    parser.add_argument("--host", default=os.environ.get("LEGIS_RJ_HOST", "127.0.0.1"))
    parser.add_argument(
        "--porta", type=int, default=int(os.environ.get("PORT", "8765"))
    )
    parser.add_argument(
        "--banco", help="caminho do SQLite (padrao: banco/legis-rj.sqlite)"
    )
    parser.add_argument(
        "--dominio",
        action="append",
        metavar="HOST",
        help="dominio publico por onde o servidor sera acessado. Sem isto, so "
             "requisicoes locais passam. Pode repetir.",
    )
    parser.add_argument(
        "--url-publica",
        metavar="URL",
        help="endereco publico completo. Ativa o fluxo OAuth, exigido pelo "
             "ChatGPT. O Claude conecta sem isto.",
    )
    args = parser.parse_args(argv)

    from .servidor import construir

    dominios = list(args.dominio or [])
    do_ambiente = os.environ.get("LEGIS_RJ_DOMINIOS", "")
    dominios += [d.strip() for d in do_ambiente.split(",") if d.strip()]

    url_publica = args.url_publica or os.environ.get("LEGIS_RJ_URL_PUBLICA")
    if url_publica and not url_publica.startswith(("http://", "https://")):
        url_publica = f"https://{url_publica}"

    ajustes = {"host": args.host, "port": args.porta} if args.http else {}
    try:
        servidor = construir(
            args.banco,
            dominios=dominios or None,
            url_publica=url_publica,
            segredo_oauth=os.environ.get("LEGIS_RJ_SEGREDO_OAUTH"),
            **ajustes,
        )
    except FileNotFoundError as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1

    if args.http:
        alcance = ", ".join(dominios) if dominios else "somente local"
        print(
            f"Legislacao do RJ em http://{args.host}:{args.porta}/mcp"
            f"  ({alcance})",
            file=sys.stderr,
        )

    servidor.run(transport="streamable-http" if args.http else "stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
