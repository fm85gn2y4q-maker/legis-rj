"""Sobe o servidor em memória e chama as ferramentas como um cliente chamaria.

Registrar no Claude Desktop e descobrir o defeito lá é caro: o erro aparece
como "servidor não iniciou", sem dizer por quê. Aqui o mesmo caminho roda com
a mensagem de erro à vista.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from legis_rj.servidor import mcp


async def main() -> None:
    ferramentas = await mcp.list_tools()
    print(f"{len(ferramentas)} ferramentas expostas:")
    for f in ferramentas:
        primeira = (f.description or "").strip().splitlines()[0]
        print(f"  {f.name:<24} {primeira[:64]}")

    print("\n--- verificar_vigencia('lei 4024/2002') ---")
    resposta = await mcp.call_tool(
        "verificar_vigencia", {"referencia": "lei 4024/2002"}
    )
    conteudo = resposta[0] if isinstance(resposta, tuple) else resposta
    texto = conteudo[0].text if isinstance(conteudo, list) else str(conteudo)
    dados = json.loads(texto)
    for v in dados.get("vigencia", []):
        print("  ", v["citacao"])
        print("   ato:", v["declarado"]["ato"])
        for tipo, trechos in v["declarado"]["dispositivos"].items():
            print(f"   {tipo}: {len(trechos)}")
        for aviso in v["avisos"]:
            print("   aviso:", aviso[:88])

    print("\n--- pesquisar_legislacao('transporte intermunicipal') ---")
    resposta = await mcp.call_tool(
        "pesquisar_legislacao", {"consulta": "transporte intermunicipal", "limite": 3}
    )
    conteudo = resposta[0] if isinstance(resposta, tuple) else resposta
    texto = conteudo[0].text if isinstance(conteudo, list) else str(conteudo)
    for ato in json.loads(texto)["atos"]:
        print(f"   {ato['citacao']} — {ato['situacao_declarada']} "
              f"({ato['origem_da_situacao']})")


if __name__ == "__main__":
    asyncio.run(main())
